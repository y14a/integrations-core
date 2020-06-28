# (C) Datadog, Inc. 2020-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from pymqi.CMQC import MQRC_NO_MSG_AVAILABLE
from pymqi.CMQCFC import MQCMD_STATISTICS_CHANNEL, MQCMD_STATISTICS_MQI, MQCMD_STATISTICS_Q
from six import iteritems

from datadog_checks.base import AgentCheck
from datadog_checks.ibm_mq.collectors.utils import CustomPCFExecute
from ..metrics import channel_stats_metrics, METRIC_PREFIX

from ..stats_wrapper import ChannelStats

try:
    import pymqi
    from pymqi import Queue
except ImportError as e:
    pymqiException = e
    pymqi = None


STATISTICS_QUEUE_NAME = 'SYSTEM.ADMIN.STATISTICS.QUEUE'


class StatsCollector(object):
    def __init__(self, check):
        # type: (AgentCheck) -> None
        self.check = check

    def collect(self, queue_manager):
        queue = Queue(queue_manager, STATISTICS_QUEUE_NAME)
        self.check.log.debug("Start stats collection")

        try:
            while True:
                bin_message = queue.get()
                message, header = CustomPCFExecute.unpack(bin_message)

                if header.Command == MQCMD_STATISTICS_CHANNEL:
                    self._collect_channel_stats(message)
                elif header.Command == MQCMD_STATISTICS_MQI:
                    self.check.log.debug('MQCMD_STATISTICS_MQI not implemented yet')
                elif header.Command == MQCMD_STATISTICS_Q:
                    self.check.log.debug('MQCMD_STATISTICS_Q not implemented yet')
                else:
                    self.check.log.debug('Unknown command: {}'.format(header.Command))
                if header.Control == pymqi.CMQCFC.MQCFC_LAST:
                    break
        except pymqi.MQMIError as err:
            if err.reason == MQRC_NO_MSG_AVAILABLE:
                pass
            else:
                raise
        finally:
            queue.close()

    def _collect_channel_stats(self, message):
        channel_stats = ChannelStats(message)
        for channel_info in channel_stats.channels:
            tags = [
                'channel:{}'.format(channel_info.name),
                'channel_type:{}'.format(channel_info.type),
                'remote_q_mgr_name:{}'.format(channel_info.remote_q_mgr_name),
                'connection_name:{}'.format(channel_info.connection_name),
            ]
            prefix = '{}.stats.channel'.format(METRIC_PREFIX)
            metrics_map = channel_stats_metrics()
            self._submit_metrics_from_properties(prefix, channel_info.raw, metrics_map, tags)

    def _submit_metrics_from_properties(self, prefix, properties, metrics_map, tags):
        for metric_name, pymqi_type in iteritems(metrics_map):
            metric_full_name = '{}.{}'.format(prefix, metric_name)
            if pymqi_type not in properties:
                self.check.log.debug("metric not found: %s", metric_name)
                continue
            metric_value = int(properties[pymqi_type])
            self.check.gauge(metric_full_name, metric_value, tags=tags)