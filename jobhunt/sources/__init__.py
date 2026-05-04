"""Job-source adapters and registry.

Adding a new source = adding a file here that subclasses `JobSource` +
one entry in `REGISTRY`. `FetchService` is unaware of which sources
exist.
"""

from jobhunt.sources.adzuna import AdzunaSource
from jobhunt.sources.arbeitnow import ArbeitnowSource
from jobhunt.sources.base import JobSource
from jobhunt.sources.bundesagentur import BundesagenturSource
from jobhunt.sources.jooble import JoobleSource
from jobhunt.sources.remotive import RemotiveSource
from jobhunt.sources.weworkremotely import WeWorkRemotelySource

REGISTRY: dict[str, type[JobSource]] = {
    BundesagenturSource.name: BundesagenturSource,
    ArbeitnowSource.name: ArbeitnowSource,
    AdzunaSource.name: AdzunaSource,
    JoobleSource.name: JoobleSource,
    RemotiveSource.name: RemotiveSource,
    WeWorkRemotelySource.name: WeWorkRemotelySource,
}

__all__ = [
    "REGISTRY",
    "AdzunaSource",
    "ArbeitnowSource",
    "BundesagenturSource",
    "JobSource",
    "JoobleSource",
    "RemotiveSource",
    "WeWorkRemotelySource",
]
