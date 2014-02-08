Docker fish completion
======================
docker command completion for the fish shell.

fish is awesome, docker is too.

Installation
------------
    mkdir ~/.config/fish/completions
    cp docker.fish ~/.config/fish/completions

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

Completions
-----------
- parameters
- commands
- containers
- images
- repositories

