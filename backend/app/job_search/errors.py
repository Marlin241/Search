class JobSearchSourceError(Exception):
    """Raised by a single job_search client when its source is unreachable
    or returns something the client cannot parse. Caught by the aggregator
    (Task 9) to omit just that source from results rather than failing the
    whole search."""
