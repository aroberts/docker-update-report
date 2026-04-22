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
                            [-c PATH] [-i REGEX] [-e REGEX] [-n] [-l] [-k STR]
                            [--cooldown-days N] [--cooldown-fallthrough]
                            [--table [PATH]] [--table-max-width N]
                            [--json [PATH]] [--json-timestamps]
                            [service_ids ...]

positional arguments:
  service_ids           restrict tool to only these service ids

options:
  -h, --help            show this help message and exit
  -d, --delay DELAY     delay in seconds between service inspections
  -f, --failure-delay DELAY
                        delay after encountering a docker rate limit [500s]
  -m, --max-attempts N  Fail after this many errors
  -v, --verbose         more logging (or -vv, etc)
  -q, --quiet           less logging
  -c, --repo-credentials PATH
                        a file containing credentials for use with `docker
                        login` in the format of `user:password` (only the
                        first line will be read)
  -i, --include-tags REGEX
                        only tags matching this regex will be considered. This
                        can be overridden per-service with the label
                        'dur.tags.include'. If this regex has capture groups,
                        they will be used to sort the tags. If named capture
                        groups are used, the sort will be in alphabetical
                        order
  -e, --exclude-tags REGEX
                        only tags matching this regex will be considered. This
                        can be overridden per-service with the label
                        'dur.tags.exclude'
  -n, --no-parse-numerics
                        don't attempt to parse numeric tag parts
  -l, --ignore-labels   ignore container labels, only use command line options
  -k, --link-template STR
                        template for creating links from tag matches. Override
                        with container label 'dur.link.template'
  --cooldown-days N     supply chain cooldown: suppress proposing a new tag
                        until it has been published for at least this many
                        days. 0 disables the cooldown (default). Override per-
                        service with label 'dur.cooldown_days'
  --cooldown-fallthrough
                        if the newest tag is in cooldown, walk back through
                        older tags (up to 3) and recommend the newest one that
                        is past cooldown. Any in-cooldown tags encountered
                        along the way are still reported in the 'cooldowns'
                        output field. Off by default (strict: in-cooldown
                        newest tag suppresses recommendation entirely).
                        Override per-service with label
                        'dur.cooldown_fallthrough'
  --table [PATH]        output results as table, to either STDOUT or a
                        provided path
  --table-max-width N   max width of table columns [50]
  --json [PATH]         output results as json, to either STDOUT or a provided
                        path
  --json-timestamps     add a `checked_at` timestamp field to each row of json
                        output
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


## Supply chain cooldown

As a defense against supply chain attacks, `docker-update-report` can enforce
a cooldown period before reporting a new tag as an available update. When
enabled, a tag must have been published for at least `cooldown_days` before
the tool will surface it. This gives the community time to vet new releases —
compromised packages are typically detected and pulled well within a month.

The cooldown is opt-in and disabled by default. Enable it globally with
`--cooldown-days N`, or override it for a single service with the
`dur.cooldown_days=<int>` label. A value of `0` disables the cooldown.

### Behavior

- If the latest tag is past cooldown → report it as usual.
- If the latest tag is still in cooldown → suppress it and log the remaining
  time at `info`.
- If the tag's publish timestamp (skopeo's `Created` field) is missing or
  unparseable → suppress it and log at `error` (fail-safe).

Suppression is strict by default: if a newer tag exists but is still cooling,
the tool does not recommend any upgrade, even to an older tag that is past
cooldown. Pass `--cooldown-fallthrough` (or set
`dur.cooldown_fallthrough=true` on the service) to walk back through older
tags (up to 3 attempts) and recommend the newest one that is past cooldown.

Regardless of mode, output includes a `cooldowns` field (column in `--table`,
key in `--json`) listing every in-cooldown tag encountered during the walk,
along with how much of its cooldown remains:

- In `--json`, `cooldowns` is a list of objects:
  `[{"tag": "v1.2.3", "remaining_days": 2.1}, ...]`. Empty list if none were
  encountered. `remaining_days` is `null` when the tag's publish timestamp
  could not be parsed (fail-safe: still treated as in cooldown).
- In `--table`, the same information is flattened to a single cell as
  `v1.2.3 (2.1d), v1.2.2 (1.3d)`. An unknown remaining period renders as
  `(?)`. Empty renders as `None`.

Without `--cooldown-fallthrough`, the walk stops at the first candidate, so
at most one entry will appear. With fallthrough enabled, up to 3 entries may
appear (one per candidate inspected before a past-cooldown tag is found).

Note that `Created` reflects when the image manifest was built, not
necessarily when it was pushed to the registry. For virtually all registries
these are effectively the same, but be aware of the distinction if you are
tracking images that get rebuilt and retagged out of band.


## Motivation

I needed an alternative to the hindsight-oriented update strategy that seems to
be popular in the Docker space. Tools like `watchtower` (or regular
docker-compose `pull`s) assume that the images are running on rolling tags
(e.g. `latest`), and that updates can be performed without breaking changes.


