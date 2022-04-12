def call(instances, discovery_request, **kwargs):
    eds = kwargs['eds']

    for instance in instances:
        yield {
            "name": instance["name"],
            "type": "STRICT_DNS",
            "connect_timeout": "5.000s",
            "tls_context": {},
            "load_assignment": {
                "cluster_name": f"{instance['name']}_cluster",
                "endpoints": eds.locality_lb_endpoints(
                        upstreams=instance["endpoints"],
                        request=discovery_request,
                        resolve_dns=False,
                ),
            },
        }
