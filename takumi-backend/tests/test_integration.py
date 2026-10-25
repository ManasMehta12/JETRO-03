from scripts.demo_flow import run_flow


def test_complete_flow_twice(client):
    run_flow(client)
    run_flow(client)
