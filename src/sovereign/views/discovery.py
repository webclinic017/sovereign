import schedule
from fastapi import Body, BackgroundTasks, HTTPException
from fastapi.routing import APIRouter
from sovereign.logs import add_log_context
from starlette.responses import Response, UJSONResponse
from sovereign import discovery
from sovereign.schemas import DiscoveryRequest, DiscoveryResponse
from sovereign.utils.auth import authenticate

router = APIRouter()


@router.post(
    '/discovery:{xds_type}',
    summary='Envoy Discovery Service Endpoint',
    response_model=DiscoveryResponse,
    responses={
        200: {
            'description': 'New resources provided'
        },
        304: {
            'description': 'Resources are up-to-date'
        }
    }
)
async def discovery_response(
        xds_type: discovery.DiscoveryTypes,
        background_tasks: BackgroundTasks,
        response_: Response,
        discovery_request: DiscoveryRequest = Body(None),
):
    background_tasks.add_task(schedule.run_pending)
    authenticate(discovery_request)

    response_.headers['X-Sovereign-Client-Version'] = discovery_request.envoy_version
    response_.headers['X-Sovereign-Requested-Resources'] = ','.join(discovery_request.resource_names)
    response_.headers['X-Sovereign-Requested-Type'] = xds_type.value

    add_log_context(
        resource_names=discovery_request.resource_names,
        envoy_ver=discovery_request.envoy_version
    )

    response: dict = await discovery.response(discovery_request, xds_type.value)
    response_.headers['X-Sovereign-Response-Version'] = response['version_info']
    if response['version_info'] == discovery_request.version_info:
        # Configuration is identical, send a Not Modified response
        return Response(status_code=304)
    elif len(response.get('resources', [])) == 0:
        raise HTTPException(status_code=404)
    elif response['version_info'] != discovery_request.version_info:
        return UJSONResponse(content=response)
    raise HTTPException(status_code=500)
