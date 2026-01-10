def set_trace():
    import socket
    import struct
    import pydevd_pycharm

    with open("/proc/net/route") as f:
        for line in f.readlines()[1:]:
            p = line.split()
            if p and p[1] == "00000000":
                gw = socket.inet_ntoa(struct.pack("<L", int(p[2], 16)))
                break
    pydevd_pycharm.settrace(host=gw, port=12345, suspend=False)
