# docker-update-report

[![License](https://img.shields.io/badge/License-MIT-%230067c2)](https://github.com/aroberts/docker-update-report/blob/master/LICENSE)

This is a small Python3 utility for identifying and reporting on running Docker
containers that have an updated image available, in some form.
`docker-update-report` tries to identify three different types of available
update:

- `restart`: For stacks deployed with docker-compose (and possibly
  docker-swarm), has a new image been pulled, such that a `docker-compose up`
  invocation would update the container?
- `pull`: Is there a new image available at the remote for this image:tag?
- `tag`: If we can parse a semantic version (semver) out of the running tag, is
  there a "newer" (bigger, really) semver-style tag available at the remote?

This tool doesn't perform any date comparisons; it only does equality checks on
the hashes (and the parsed version tags, for semver-updates). This is partly
for simplicity, but also because the docker API is fairly rate-limited, and
adding additional inspections per container would quickly balloon the call
volume.

In the output, `null`/`None` is used to indicate that not enough information
was available to make a determination, or the field is not applicable. For
example, if a semver-style version string can't be parsed out of the running
tag, then no tag comparison is done. Or, if a container is running is not part
of a docker-compose stack, then the compose-related section is ignored.


## Installation

`docker-update-report` is a self-contained python script, just download it and
run it.

This tool has no python dependencies, but some external dependencies. First, the
user running the tool must be able to run `docker` and `docker-compose`.
Second, this tool uses [`skopeo`](https://github.com/containers/skopeo)
(available via most package managers) to navigate the remote container repo
APIs.

## Usage
```
usage: docker-update-report [-h] [-d DELAY] [-f DELAY] [-m N] [-v] [-q]
                            [-c PATH] [-o [ID ...]] [--table [PATH]]
                            [--table-max-width N] [--json [PATH]]

A utility for inspecting docker-compose stacks against their source image
hashes and tags, and determining what needs updates.

optional arguments:
  -h, --help            show this help message and exit
  -d DELAY, --delay DELAY
                        delay in seconds between container inspections
  -f DELAY, --failure-delay DELAY
                        delay after encountering a docker rate limit [500s]
  -m N, --max-attempts N
                        Fail after this many errors
  -v, --verbose         more logging (or -vv, etc)
  -q, --quiet           less logging
  -c PATH, --repo-credentials PATH
                        a file containing credentials for use with `docker
                        login` in the format of `user:password` (only the
                        first line will be read)
  -o [ID ...], --only [ID ...]
                        restrict tool to only these container ids
  --table [PATH]        output results as table, to either STDOUT or a
                        provided path
  --table-max-width N   max width of table columns [50]
  --json [PATH]         output results as json, to either STDOUT or a provided
                        path
```

Because of the docker-compose dependency, and the way compose information is
scraped from the docker socket, this tool needs to be run locally. Invoking
with `$DOCKER_HOST` or `docker context` in play is unlikely to work, if any
containers have been deployed to that docker socket with `docker-compose`.

## Dockerhub rate limit

This tool includes several faculties for working around dockerhub's [API rate
limit](https://www.docker.com/blog/checking-your-current-docker-pull-rate-limits-and-status/):

- allow the tool to log in via `--repo-credentials` (note: this uses shell
  `docker login` and will potentially change `~/.docker/config.json`)
- insert a delay between queries via `--delay` (specified in seconds)
- retry after failures with `--max-attempts N` (limited to N attempts)
- delay before retrying after failures via `--failure-delay` (in seconds)


## Motivation

I needed an alternative to the hindsight-oriented update strategy that seems to
be popular in the Docker space. Tools like `watchtower` (or regular
docker-compose `pull`s) assume that the images are running on rolling tags
(e.g. `latest`), and that updates can be performed without breaking changes.


