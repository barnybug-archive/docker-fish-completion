#!/usr/bin/env python
import subprocess
import re
import os
from argparse import ArgumentParser


class Subcommand(object):
    def __init__(self, command, description, args, switches):
        self.command = command
        self.description = description
        self.args = args
        self.switches = switches


class Switch(object):
    def __init__(self, shorts, longs, description, metavar):
        self.shorts = shorts
        self.longs = longs
        self.description = description
        self.metavar = metavar

    def is_file_target(self):
        if not self.metavar:
            return False
        return self.metavar == 'FILE' or 'PATH' in self.metavar

    @property
    def fish_completion(self):
        complete_arg_spec = ['-s %s' % x for x in self.shorts]
        complete_arg_spec += ['-l %s' % x for x in self.longs]
        if not self.is_file_target():
            complete_arg_spec.append('-f')
        desc = repr(self.description)
        return '''{0} -d {1}'''.format(' '.join(complete_arg_spec), desc)


class DockerCmdLine(object):
    binary = 'docker'

    def __init__(self, docker_path):
        self.docker_path = docker_path

    def get_output(self, *args):
        cmd = [os.path.join(self.docker_path, self.binary)] + list(args)
        # docker returns non-zero exit code for some help commands so can't use subprocess.check_output here
        ps = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = ps.communicate()
        out = out.decode('utf-8')
        return iter(out.splitlines())

    def parse_switch(self, line):
        line = line.strip()
        if '  ' not in line:
            # ignore continuation lines
            return None
        opt, description = re.split('  +', line, 1)
        switches = opt.split(', ')
        metavar = None
        # handle arguments with metavar
        # Options:
        # -f, --file FILE
        for i, switch in enumerate(switches):
            if ' ' in switch:
                switches[i], metavar = switch.split(' ')
        shorts = [x[1:] for x in switches if not x.startswith('--')]
        longs = [x[2:] for x in switches if x.startswith('--')]
        return Switch(shorts, longs, description, metavar)

    def common_options(self):
        lines = self.get_output('-h')
        # skip header
        while next(lines) != 'Options:':
            pass

        for line in lines:
            if line == 'Commands:':
                break
            switch = self.parse_switch(line)
            if switch:
                yield switch

    def subcommands(self):
        lines = self.get_output('help')
        while next(lines) != 'Commands:':
            pass

        for line in lines:
            if not line:
                break
            command, description = line.strip().split(None, 1)
            yield self.subcommand(command, description)

    def subcommand(self, command, description):
        lines = self.get_output('help', command)
        usage = None
        for line in lines:
            if line.startswith('Usage:'):
                usage = line
                break
        else:
            raise RuntimeError(
                "Can't find Usage in command: %r" % command
            )
        args = usage.split()[3:]
        if args and args[0].upper() == '[OPTIONS]':
            args = args[1:]
        if command in ('push', 'pull'):
            # improve completion for docker push/pull
            args = ['REPOSITORY|IMAGE']
        elif command == 'images':
            args = ['REPOSITORY']
        switches = []
        for line in lines:
            if not line.strip().startswith('-'):
                continue
            switches.append(self.parse_switch(line))
        return Subcommand(command, description, args, switches)


class DockerComposeCmdLine(DockerCmdLine):
    binary = 'docker-compose'


class BaseFishGenerator(object):
    header_text = ''

    def __init__(self, docker):
        self.docker = docker

    # Generate fish completions definitions for docker
    def generate(self):
        self.header()
        self.common_options()
        self.subcommands()

    def header(self):
        cmds = sorted(sub.command for sub in self.docker.subcommands())
        print(self.header_text.lstrip() % ' '.join(cmds))

    def common_options(self):
        print('# common options')
        for switch in self.docker.common_options():
            print('''complete -c {binary} -n '__fish_docker_no_subcommand' {completion}'''.format(
                binary=self.docker.binary,
                completion=switch.fish_completion))
        print()

    def subcommands(self):
        print('# subcommands')
        for sub in self.docker.subcommands():
            print('# %s' % sub.command)
            desc = repr(sub.description)
            print('''complete -c {binary} -f -n '__fish_docker_no_subcommand' -a {command} -d {desc}'''.format(
                binary=self.docker.binary,
                command=sub.command,
                desc=desc))
            for switch in sub.switches:
                print('''complete -c {binary} -A -n '__fish_seen_subcommand_from {command}' {completion}'''.format(
                    binary=self.docker.binary,
                    command=sub.command,
                    completion=switch.fish_completion))

            # standalone arguments
            unique = set()
            for args in sub.args:
                m = re.match(r'\[(.+)\.\.\.\]', args)
                if m:
                    # optional arguments
                    args = m.group(1)
                unique.update(args.split('|'))
            for arg in sorted(unique):
                self.process_subcommand_arg(sub, arg)
            print()
        print()

    def process_subcommand_arg(self, sub, arg):
        pass


class DockerFishGenerator(BaseFishGenerator):
    header_text = """
# docker.fish - docker completions for fish shell
#
# This file is generated by gen_docker_fish_completions.py from:
# https://github.com/barnybug/docker-fish-completion
#
# To install the completions:
# mkdir -p ~/.config/fish/completions
# cp docker.fish ~/.config/fish/completions
#
# Completion supported:
# - parameters
# - commands
# - containers
# - images
# - repositories

function __fish_docker_no_subcommand --description 'Test if docker has yet to be given the subcommand'
    for i in (commandline -opc)
        if contains -- $i %s
            return 1
        end
    end
    return 0
end

function __fish_print_docker_containers --description 'Print a list of docker containers' -a select
    switch $select
        case running
            docker ps --no-trunc --filter status=running --format '{{.ID}}\\n{{.Names}}' | tr ',' '\\n'
        case stopped
            docker ps --no-trunc --filter status=exited --filter status=created --format '{{.ID}}\\n{{.Names}}' | tr ',' '\\n'
        case all
            docker ps --no-trunc --all --format '{{.ID}}\\n{{.Names}}' | tr ',' '\\n'
    end
end

function __fish_print_docker_images --description 'Print a list of docker images'
    docker images --format '{{if eq .Repository "<none>"}}{{.ID}}\\tUnnamed Image{{else}}{{.Repository}}:{{.Tag}}{{end}}'
end

function __fish_print_docker_repositories --description 'Print a list of docker repositories'
    docker images --format '{{.Repository}}' | command grep -v '<none>' | command sort | command uniq
end
"""

    def process_subcommand_arg(self, sub, arg):
        if arg == 'CONTAINER' or arg == '[CONTAINER...]':
            if sub.command in ('start', 'rm'):
                select = 'stopped'
            elif sub.command in ('commit', 'diff', 'export', 'inspect'):
                select = 'all'
            else:
                select = 'running'
            print('''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_containers {1})' -d "Container"'''.format(sub.command, select))
        elif arg == 'IMAGE':
            print('''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_images)' -d "Image"'''.format(sub.command))
        elif arg == 'REPOSITORY':
            print('''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_repositories)' -d "Repository"'''.format(sub.command))


class DockerComposeFishGenerator(BaseFishGenerator):
    header_text = """
# docker-compose.fish - docker completions for fish shell
#
# This file is generated by gen_docker_fish_completions.py from:
# https://github.com/barnybug/docker-fish-completion
#
# To install the completions:
# mkdir -p ~/.config/fish/completions
# cp docker-compose.fish ~/.config/fish/completions
#
# Completion supported:
# - parameters
# - commands
# - services

function __fish_docker_no_subcommand --description 'Test if docker has yet to be given the subcommand'
    for i in (commandline -opc)
        if contains -- $i %s
            return 1
        end
    end
    return 0
end

function __fish_print_docker_compose_services --description 'Print a list of docker-compose services'
    docker-compose config --services ^/dev/null | command sort
end
"""

    def process_subcommand_arg(self, sub, arg):
        if arg in ('SERVICE', '[SERVICE...]'):
            print('''complete -c docker-compose -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_compose_services)' -d "Service"'''.format(sub.command))



def main():
    parser = ArgumentParser()
    parser.add_argument(
        'binary',
        choices=('docker', 'docker-compose')
    )
    parser.add_argument(
        '--docker-path',
        default='/usr/bin'
    )

    args = parser.parse_args()

    if args.binary == 'docker':
        DockerFishGenerator(DockerCmdLine(args.docker_path)).generate()
    else:
        DockerComposeFishGenerator(DockerComposeCmdLine(args.docker_path)).generate()

if __name__ == '__main__':
    main()

# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'attach' --description "Attach to a running container"
# complete -f -n '__fish_seen_subcommand_from attach' -c docker -l no-stdin --description "Do not attach stdin"
# complete -f -n '__fish_seen_subcommand_from attach' -c docker -l sig-proxy --description "Proxify all received signal to the process (even in non-tty mode)"

# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'build' --description "Build a container from a Dockerfile"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'commit' --description "Create a new image from a container's changes"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'cp' --description "Copy files/folders from the containers filesystem to the host path"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'diff' --description "Inspect changes on a container's filesystem"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'events' --description "Get real time events from the server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'export' --description "Stream the contents of a container as a tar archive"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'history' --description "Show the history of an image"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'images' --description "List images"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'import' --description "Create a new filesystem image from the contents of a tarball"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'info' --description "Display system-wide information"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'insert' --description "Insert a file in an image"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'inspect' --description "Return low-level information on a container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'kill' --description "Kill a running container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'load' --description "Load an image from a tar archive"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'login' --description "Register or Login to the docker registry server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'logs' --description "Fetch the logs of a container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'port' --description "Lookup the public-facing port which is NAT-ed to PRIVATE_PORT"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'ps' --description "List containers"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'pull' --description "Pull an image or a repository from the docker registry server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'push' --description "Push an image or a repository to the docker registry server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'restart' --description "Restart a running container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'rm' --description "Remove one or more containers"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'rmi' --description "Remove one or more images"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'run' --description "Run a command in a new container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'save' --description "Save an image to a tar archive"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'search' --description "Search for an image in the docker index"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'start' --description "Start a stopped container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'stop' --description "Stop a running container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'tag' --description "Tag an image into a repository"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'top' --description "Lookup the running processes of a container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'version' --description "Show the docker version information"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'wait' --description "Block until a container stops, then print its exit code"
