def set_trace():
    import pydevd_pycharm

    # this ip address is for the gateway IP, equivalent to host.docker.internal which
    #  isn't available on all platforms
    gateway_ip = "172.17.0.1"
    pydevd_pycharm.settrace(
        host=gateway_ip,
        port=12345,  # Use the same port number configured in PyCharm
        stdoutToServer=True,
        stderrToServer=True,
        suspend=False,
    )
