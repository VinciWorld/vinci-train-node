import asyncio

from typing import Any

from pydantic import ValidationError
from domains.Train.schemas.train_node import TrainNode, TrainNodeInfo, TrainNodeMetrics, TrainNodeState, TrainNodeStatus


class ETCDClient():
    def __init__(self, etcd_client: Any):
        self.etcd_client = etcd_client

    def register_train_node(self, key:str, data:TrainNodeStatus):
        self.etcd_client.put(key, data.model_dump_json)

    def discover_services(self, key: str):
        return self.etcd_client.get(key)
    
    def discover_all_services_with_prefix(self, prefix: str):
        services = {}
        #Example prefix = 'train_nodes/
        for value, metadata in self.etcd_client.get_prefix(prefix):
            print(metadata.key.decode('utf-8'))
            services[metadata.key.decode('utf-8').split('/')[-1]] = value.decode('utf-8')
        
        return services
    
    def register_with_lease(self, key: str, data: TrainNodeStatus, lease_time: int):
        lease = self.etcd_client.lease(lease_time)
        self.etcd_client.put(key, data.model_dump_json(), lease=lease)
        
        # Return the lease for further renewals
        return lease

    async def renew_lease_and_update_status(self, lease):
        while True:
            await asyncio.sleep(45)  # Asynchronous sleep
            lease.refresh()

    def register_train_node_with_lease(
            self,
            node_id: str,
            info: TrainNodeInfo,
            state: TrainNodeState,
            metrics: TrainNodeMetrics,
            lease_time: int
        ):

        lease = self.etcd_client.lease(lease_time)
        info_key = f"train_nodes/{node_id}/info"
        self.etcd_client.put(info_key, info.model_dump_json(), lease)

        state_key = f"train_nodes/{node_id}/state"
        self.etcd_client.put(state_key, state.model_dump_json(), lease)

        metrics_key = f"train_nodes/{node_id}/metrics"
        self.etcd_client.put(metrics_key, metrics.model_dump_json(), lease)

        return lease

    def get_train_node_info(self, node_id: str) -> dict:
        info_key = f"train_node/{node_id}/info"
        return {info_key: self.etcd_client.get(info_key).value}

    def get_train_node_run_status(self, node_id: str, run_id: str) -> dict:
        status_key = f"train_node/{node_id}/{run_id}/status"
        return {status_key: self.etcd_client.get(status_key).value}

    def get_train_node_state(self, node_id: str) -> dict:
        state_key = f"train_node/{node_id}/state"
        return {state_key: self.etcd_client.get(state_key).value}

    def get_train_node_metrics(self, node_id: str) -> dict:
        metrics_key = f"train_node/{node_id}/metrics"
        return {metrics_key: self.etcd_client.get(metrics_key).value}
    
    def put_train_node_info(self, node_id: str, info: TrainNodeInfo):
        info_key = f"train_node/{node_id}/info"
        self.etcd_client.put(info_key, info.model_dump_json())

    def put_train_node_run_status(self, node_id: str, run_id: str, status: TrainNodeStatus):
        status_key = f"train_node/{node_id}/{run_id}/status"
        self.etcd_client.put(status_key, status.model_dump_json())

    def put_train_node_state(self, node_id: str, state: TrainNodeState):
        state_key = f"train_node/{node_id}/state"
        self.etcd_client.put(state_key, state.model_dump_json())

    def put_train_node_metrics(self, node_id: str, metrics: TrainNodeMetrics):
        metrics_key = f"train_node/{node_id}/metrics"
        self.etcd_client.put(metrics_key, metrics.model_dump_json())

    def get_all_train_node_data_dict(self, node_id: str) -> dict:
        data = {}
        data.update(self.get_train_node_info(node_id))
        data.update(self.get_train_node_state(node_id))
        data.update(self.get_train_node_metrics(node_id))
        # Assuming you have a way to get all run_ids for a node
        for run_id in self.get_all_run_ids_for_node(node_id):
            data.update(self.get_train_node_run_status(node_id, run_id))
        return data

    def discover_all_train_nodes(self):
        nodes = {}
        # Example prefix = 'train_nodes/
        for value, metadata in self.etcd_client.get_prefix('train_nodes/'):
            parts = metadata.key.decode('utf-8').split('/')
            node_id = parts[1]
            if node_id not in nodes:
                nodes[node_id] = {
                    "node_id": node_id,
                    "runs": {}
                }
            sub_key = parts[-1]
            
            json_data = value.decode('utf-8')
            print(f"subkey:{sub_key} : {json_data}")
            try:
                if sub_key == "info":
                    nodes[node_id][sub_key] = TrainNodeInfo.parse_raw(json_data)
                elif sub_key == "state":
                    nodes[node_id][sub_key] = TrainNodeState.parse_raw(json_data)
                elif sub_key == "metrics":
                    nodes[node_id][sub_key] = TrainNodeMetrics.parse_raw(json_data)
                elif sub_key == "status":
                    nodes[node_id][sub_key] = TrainNodeStatus.parse_raw(json_data)
                else:
                    # Assuming it's a run_id
                    nodes[node_id]["runs"][sub_key] = TrainNodeStatus.parse_raw(json_data)
            except ValidationError as e:
                print(f"Error parsing data for key {metadata.key}: {e}")
                continue

        # Convert the dictionaries to TrainNode instances
        return {node_id: TrainNode(**data) for node_id, data in nodes.items()}