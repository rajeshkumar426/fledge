# -*- coding: utf-8 -*-

# FLEDGE_BEGIN
# See: http://fledge.readthedocs.io/
# FLEDGE_END
import datetime
from aiohttp import web

from fledge.common.storage_client.payload_builder import PayloadBuilder
from fledge.services.core import connect
from fledge.services.core.scheduler.scheduler import Scheduler

__author__ = "Amarendra K. Sinha, Ashish Jabble"
__copyright__ = "Copyright (c) 2017 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_help = """
    -------------------------------------------------------------------------------
    | GET             | /fledge/statistics                                       |
    | GET             | /fledge/statistics/history                               |
    -------------------------------------------------------------------------------
"""


#################################
#  Statistics
#################################


async def get_statistics(request):
    """
    Args:
        request:

    Returns:
            a general set of statistics

    :Example:
            curl -X GET http://localhost:8081/fledge/statistics
    """
    payload = PayloadBuilder().SELECT(("key", "description", "value")).ORDER_BY(["key"]).payload()
    storage_client = connect.get_storage_async()
    result = await storage_client.query_tbl_with_payload('statistics', payload)
    return web.json_response(result['rows'])


async def get_statistics_history(request):
    """
    Args:
        request:

    Returns:
            a list of general set of statistics

    :Example:
            curl -X GET http://localhost:8081/fledge/statistics/history?limit=1
            curl -X GET http://localhost:8081/fledge/statistics/history?key=READINGS
            curl -X GET http://localhost:8081/fledge/statistics/history?key=READINGS,PURGED,UNSENT&minutes=60
    """
    storage_client = connect.get_storage_async()
    # To find the interval in secs from stats collector schedule
    scheduler_payload = PayloadBuilder().SELECT("schedule_interval").WHERE(
        ['process_name', '=', 'stats collector']).payload()
    result = await storage_client.query_tbl_with_payload('schedules', scheduler_payload)
    if len(result['rows']) > 0:
        scheduler = Scheduler()
        interval_days, interval_dt = scheduler.extract_day_time_from_interval(result['rows'][0]['schedule_interval'])
        interval = datetime.timedelta(days=interval_days, hours=interval_dt.hour, minutes=interval_dt.minute, seconds=interval_dt.second)
        interval_in_secs = interval.total_seconds()
    else:
        raise web.HTTPNotFound(reason="No stats collector schedule found")
    stats_history_chain_payload = PayloadBuilder().SELECT(("history_ts", "key", "value"))\
        .ALIAS("return", ("history_ts", 'history_ts')).FORMAT("return", ("history_ts", "YYYY-MM-DD HH24:MI:SS.MS"))\
        .ORDER_BY(['history_ts', 'desc']).WHERE(['1', '=', 1]).chain_payload()

    if 'key' in request.query:
        key = request.query['key']
        split_list = key.split(',')
        stats_history_chain_payload = PayloadBuilder(stats_history_chain_payload).AND_WHERE(
            ['key', '=', split_list[0]]).chain_payload()
        del split_list[0]
        for i in split_list:
            stats_history_chain_payload = PayloadBuilder(stats_history_chain_payload).OR_WHERE(
                ['key', '=', i]).chain_payload()
    try:
        # get time based graphs for statistics history
        val = 0
        if 'minutes' in request.query and request.query['minutes'] != '':
            val = int(request.query['minutes']) * 60
        elif 'hours' in request.query and request.query['hours'] != '':
            val = int(request.query['hours']) * 60 * 60
        elif 'days' in request.query and request.query['days'] != '':
            val = int(request.query['days']) * 24 * 60 * 60

        if val < 0:
            raise ValueError
        elif val > 0:
            stats_history_chain_payload = PayloadBuilder(stats_history_chain_payload).AND_WHERE(['history_ts', 'newer', val]).chain_payload()
    except ValueError:
        raise web.HTTPBadRequest(reason="Time unit must be a positive integer")

    if 'limit' in request.query and request.query['limit'] != '':
        try:
            limit = int(request.query['limit'])
            if limit < 0:
                raise ValueError
            if 'key' in request.query:
                limit_count = limit
            else:
                # FIXME: Hack straight away multiply the LIMIT by the group count
                # i.e. if there are 8 records per distinct (stats_key), and limit supplied is 2
                # then internally, actual LIMIT = 2*8
                # TODO: FOGL-663 Need support for "subquery" from storage service
                # Remove python side handling date_trunc and use
                # SELECT date_trunc('second', history_ts::timestamptz)::varchar as history_ts

                count_payload = PayloadBuilder().AGGREGATE(["count", "*"]).payload()
                result = await storage_client.query_tbl_with_payload("statistics", count_payload)
                key_count = result['rows'][0]['count_*']
                limit_count = limit * key_count
            stats_history_chain_payload = PayloadBuilder(stats_history_chain_payload).LIMIT(limit_count).chain_payload()
        except ValueError:
            raise web.HTTPBadRequest(reason="Limit must be a positive integer")

    stats_history_payload = PayloadBuilder(stats_history_chain_payload).payload()
    result_from_storage = await storage_client.query_tbl_with_payload('statistics_history', stats_history_payload)
    group_dict = []
    for row in result_from_storage['rows']:
        new_dict = {'history_ts': row['history_ts'], row['key']: row['value']}
        group_dict.append(new_dict)

    results = []
    temp_dict = {}
    previous_ts = None
    for row in group_dict:
        # first time or when history_ts changes
        if previous_ts is None or previous_ts != row['history_ts']:
            if previous_ts is not None:
                results.append(temp_dict)
            previous_ts = row['history_ts']
            temp_dict = {'history_ts': previous_ts}

        # Append statistics key to temp dict
        for key, value in row.items():
            temp_dict.update({key: value})

    # Append the last set of records which do not get appended above
    results.append(temp_dict)
    return web.json_response({"interval": interval_in_secs, 'statistics': results})
