def set_trace():
    import debugpy

    # Listen on all interfaces at port 5678
    debugpy.listen(("172.17.0.1", 12345))
    print("Waiting for debugger to attach...")
    debugpy.wait_for_client()  # Optional: pause execution until VS Code attaches
