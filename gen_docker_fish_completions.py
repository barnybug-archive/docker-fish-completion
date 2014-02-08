#!/usr/bin/env python

import subprocess
import re

class Subcommand(object):
    def __init__(self, command, description, args, switches):
        self.command = command
        self.description = description
        self.args = args
        self.switches = switches

class Switch(object):
    def __init__(self, shorts, longs, description):
        self.shorts = shorts
        self.longs = longs
        self.description = description

    @property
    def fish_completion(self):
        complete_arg_spec = ['-s %s' % x for x in self.shorts]
        complete_arg_spec += ['-l %s' % x for x in self.longs]
        desc = repr(self.description)
        return '''{0} -d {1}'''.format(' '.join(complete_arg_spec), desc)

class DockerCmdLine(object):
    def get_output(self, *args):
        # docker returns non-zero exit code for some help commands so can't use subprocess.check_output here
        ps = subprocess.Popen(['/usr/bin/docker'] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = ps.communicate()
        return iter(out.splitlines())

    def parse_switch(self, line):
        opt, description = line.strip().split(': ', 1)
        switches, default = opt.split('=')
        switches = switches.split(', ')
        shorts = [x[1:] for x in switches if not x.startswith('--')]
        longs = [x[2:] for x in switches if x.startswith('--')]
        return Switch(shorts, longs, description)

    def common_options(self):
        lines = self.get_output('-h')
        next(lines)
        for line in lines:
            yield self.parse_switch(line)

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
        next(lines)
        usage = next(lines) # Usage: docker x [OPTIONS] a b c
        args = usage.split()[3:]
        if args and args[0] == '[OPTIONS]':
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

class FishGenerator(object):
    def __init__(self, docker, fout):
        self.docker = docker
        self.fout = fout

    # Generate fish completions definitions for docker
    def generate(self):
        self.header()
        self.common_options()
        self.subcommands()

    def header(self):
        print """# docker.fish - docker completions for fish shell

function __fish_docker_no_subcommand --description 'Test if docker has yet to be given the subcommand'
    for i in (commandline -opc)
        if contains -- $i attach build commit cp diff events export history images import info insert inspect kill load login logs port ps pull push restart rm rmi run save search start stop tag top version wait
            return 1
        end
    end
    return 0
end

function __fish_print_docker_containers --description 'Print a list of docker containers' -a select
    switch $select
        case running
            docker ps -a --no-trunc | awk 'NR>1' | awk 'BEGIN {FS="  +"}; $5 ~ "^Up" {print $1 "\\n" $(NF-1)}' | tr ',' '\\n'
        case stopped
            docker ps -a --no-trunc | awk 'NR>1' | awk 'BEGIN {FS="  +"}; $5 ~ "^Exit" {print $1 "\\n" $(NF-1)}' | tr ',' '\\n'
        case all
            docker ps -a --no-trunc | awk 'NR>1' | awk 'BEGIN {FS="  +"}; {print $1 "\\n" $(NF-1)}' | tr ',' '\\n'
    end
end

function __fish_print_docker_images --description 'Print a list of docker images'
    docker images | awk 'NR>1' | grep -v '<none>' | awk '{print $1":"$2}'
end

function __fish_print_docker_repositories --description 'Print a list of docker repositories'
    docker images | awk 'NR>1' | grep -v '<none>' | awk '{print $1}' | sort | uniq
end
"""

    def common_options(self):
        print '# common options'
        for switch in self.docker.common_options():
            print '''complete -c docker -f -n '__fish_docker_no_subcommand' {0}'''.format(switch.fish_completion)
        print

    def subcommands(self):
        print '# subcommands'
        for sub in self.docker.subcommands():
            print '# %s' % sub.command
            desc = repr(sub.description)
            print '''complete -c docker -f -n '__fish_docker_no_subcommand' -a {0} -d {1}'''.format(sub.command, desc)
            for switch in sub.switches:
                print '''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' {1}'''.format(sub.command, switch.fish_completion)

            # standalone arguments
            unique = set()
            for args in sub.args:
                m = re.match(r'\[(.+)\.\.\.\]', args)
                if m:
                    # optional arguments
                    args = m.group(1)
                unique.update(args.split('|'))

            for arg in unique:
                if arg == 'CONTAINER' or arg == '[CONTAINER...]':
                    if sub.command in ('start', 'rm'):
                        select = 'stopped'
                    elif sub.command in ('commit', 'diff', 'export'):
                        select = 'all'
                    else:
                        select = 'running'
                    print '''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_containers {1})' -d "Container"'''.format(sub.command, select)
                elif arg == 'IMAGE':
                    print '''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_images)' -d "Image"'''.format(sub.command)
                elif arg == 'REPOSITORY':
                    print '''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_repositories)' -d "Repository"'''.format(sub.command)
            print

        print



if __name__ == '__main__':
    with file('docker.fish', 'w') as fout:
        FishGenerator(DockerCmdLine(), fout).generate()

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
