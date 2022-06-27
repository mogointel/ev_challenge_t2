import datetime

server_time_start = datetime.datetime.now()
server_time_base = datetime.datetime(year=2022, month=6, day=8, hour=9, minute=55)

server_time_rate = 1

def server_now():
    curr_time = datetime.datetime.now()
    offset_seconds = (curr_time - server_time_start).seconds
    offset = datetime.timedelta(seconds=offset_seconds * server_time_rate)
    server_time = server_time_base + offset
    return server_time
