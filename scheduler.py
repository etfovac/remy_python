#!/usr/bin/env/python3

# Potential alternatives:
# Use cron, available on Raspberry Pi Raspbian Linux don't need to worry about Windows
# flask-apscheduler adds support for flask context but I think that's not needed here
# https://apscheduler.readthedocs.io/en/latest/userguide.html
from apscheduler.schedulers.background import BackgroundScheduler

from remote_command import RemoteCommand
from ir_remote import transmit_command_ir
import quiet_times

from datetime import datetime
from datetime import timedelta

import service_constants
from flask import jsonify


class Scheduler:
    """
    Use a class to enable easy reuse of a single apscheduler instance
    """

    cron = 'cron'
    day_of_week = 'mon-sun'

    def __init__(self):
        self.background_scheduler = BackgroundScheduler()
        # apscheduler job store- use default MemoryJobStore, in memory, not persisted
        # apscheduler executor- use default

        # can add jobs before or after starting scheduler
        self.background_scheduler.start()

    def schedule_jobs(self):
        """ Calls remote control functions based on time of day
        """
        self.add_jobs_ir_remote()

    def add_jobs_ir_remote(self):
        """
        https://apscheduler.readthedocs.io/en/latest/modules/triggers/cron.html#module-apscheduler.triggers.cron
        """
        times = quiet_times.get_quiet_times('./data/quiet_times.json')

        # self.add_jobs_volume(times)
        self.add_jobs_mute(times)

    def add_jobs_volume(self, quiet_times):

        for quiet_time in quiet_times:

            # explicitly instantiating CronTrigger is more verbose but I hoped it would be more clear
            # trigger_start = CronTrigger(hour=quiet_time.start.hour,
            #                             minute=quiet_time.start.minute,
            #                             second=quiet_time.start.second)
            # add_job with a pre instantiated trigger didn't work, I didn't figure out correct syntax
            # scheduler.add_job(transmit_command_ir, cron, trigger_start, args=[RemoteCommand.VOLUME_DECREASE])
            # scheduler.add_job(transmit_command_ir_volume_decrease, cron, trigger_start)

            # add_job, implicitly create the trigger
            # args is for function transmit_command_ir
            self.background_scheduler.add_job(transmit_command_ir, Scheduler.cron,
                                              day_of_week=Scheduler.day_of_week,
                                              hour=quiet_time.start.hour, minute=quiet_time.start.minute,
                                              second=quiet_time.start.second,
                                              args=[RemoteCommand.VOLUME_DECREASE])
            self.background_scheduler.add_job(transmit_command_ir, Scheduler.cron,
                                              day_of_week=Scheduler.day_of_week,
                                              hour=quiet_time.end.hour, minute=quiet_time.end.minute,
                                              second=quiet_time.end.second,
                                              args=[RemoteCommand.VOLUME_INCREASE])

    def add_jobs_mute(self, quiet_times):
        """ mute sound during each quiet time
        """

        for quiet_time in quiet_times:
            # add_job, implicitly create the trigger
            # args is for function transmit_command_ir
            # first call to mute toggles sound off
            self.background_scheduler.add_job(transmit_command_ir, Scheduler.cron,
                                              day_of_week=Scheduler.day_of_week,
                                              hour=quiet_time.start.hour, minute=quiet_time.start.minute,
                                              second=quiet_time.start.second,
                                              args=[RemoteCommand.MUTE])
            # next call to mute toggles sound on
            self.background_scheduler.add_job(transmit_command_ir, Scheduler.cron,
                                              day_of_week=Scheduler.day_of_week,
                                              hour=quiet_time.end.hour, minute=quiet_time.end.minute,
                                              second=quiet_time.end.second,
                                              args=[RemoteCommand.MUTE])

    def volume_decrease_increase(self, duration_seconds, decrease_count=4, increase_count=3):
        """
        decreases volume for duration_seconds, then increases volume
        :param duration_seconds: time between last decrease volume and first increase volume
            e.g. caller can pass duration of commercial
        :param decrease_count: number of times to send volume decrease command
        ok if decrease_count is greater than number needed to decrease volume to silent.
        :param increase_count: number of times to send volume increase command
        """

        # may be used to allow time to transmit command
        command_transmission_delay_seconds = 1

        # Use scheduler instead of sleep() to keep app service responsive to other requests

        for i in range(0, decrease_count):
            run_date = datetime.now() + timedelta(seconds=i * command_transmission_delay_seconds)
            # add_job, implicitly create the trigger
            # args is for function transmit_command_ir
            self.background_scheduler.add_job(transmit_command_ir, 'date', run_date=run_date,
                                              args=[RemoteCommand.VOLUME_DECREASE])

        duration_seconds = 15 if duration_seconds is None else duration_seconds

        for i in range(0, increase_count):
            run_date = datetime.now() + timedelta(seconds=(duration_seconds + (i * command_transmission_delay_seconds)))
            self.background_scheduler.add_job(transmit_command_ir, 'date', run_date=run_date,
                                              args=[RemoteCommand.VOLUME_INCREASE])

        # TODO: consider extract a helper method to construct a response e.g. flask_response(response_string)
        data = {service_constants.API_NAME_KEY: service_constants.API_NAME,
                service_constants.VERSION_KEY: service_constants.VERSION,
                service_constants.MESSAGE_KEY: 'volume-decrease-increase'}

        return jsonify(data)

