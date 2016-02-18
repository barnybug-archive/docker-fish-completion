Docker fish completion
======================
docker command completion for the fish shell.

- fish = awesome
- docker = awesome
- completion = awesome²

Installation
------------
    mkdir ~/.config/fish/completions
    wget https://raw.github.com/barnybug/docker-fish-completion/master/docker.fish -O ~/.config/fish/completions/docker.fish

### [Fisherman](https://github.com/fisherman/fisherman)

    fisher install barnybug/docker-fish-completion

fish will show up the new completions straight away, no reload necessary.
    
Example
-------
    % docker run -[TAB]
    --attach          (Attach to stdin, stdout or stderr.)
    ...

    % docker run -t -i [TAB]
        busybox:latest             (Image)
        ubuntu:12.04               (Image)

    % docker run -t -i busybox:latest
    / #

Completion supported
--------------------
- parameters
- commands
- containers
- images
- repositories

