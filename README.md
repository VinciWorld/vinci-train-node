## Train Node README

### Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Key Responsibilities](#key-responsibilities)
4. [Scalability](#scalability)
5. [Local Environment Setup](#local-setup)
6. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Local Setup](#local-setup)
   - [Environment Configuration](#environment-configuration)
7. [Conclusion](#conclusion)
---

### Overview <a name="overview"></a>
The train node serves as the computational backbone of our machine learning training ecosystem. It interfaces with Unity environments and ML Agents to train machine learning models based on the jobs sourced from the central node.

### Architecture <a name="architecture"></a>
Embedded within a scalable infrastructure, the train node incorporates various technologies such as RabbitMQ for job consumption, WebSocket for real-time communication, and Redis for state maintenance across the system.

### Key Responsibilities <a name="key-responsibilities"></a>
1. **ML Training**: Leverages Unity and ML Agents to execute the actual training of machine learning models.
2. **Job Consumption**: Interfaces with RabbitMQ on AWS, ingesting training jobs dispatched by the central node.
3. **Environment Management**: On receiving a training job, it initiates the specified Unity training environment configured as a dedicated server.
4. **Real-time Data Bridging**: Once the Unity instance is up and running, a WebSocket connection is established to funnel data between the Unity environment and the central node, essentially acting as a data bridge.

### Scalability <a name="scalability"></a>
The train node is meticulously crafted with scalability in mind. Not only can it concurrently initiate multiple Unity instances for simultaneous training of various models, optimizing resource utilization and curtailing total training duration, but its architecture also promotes effortless horizontal scaling.

The design paradigm ensures that scaling the train nodes is straightforward. Given their primary function of fetching jobs from the queue and processing them, users can conveniently deploy train nodes on their personal computers or other systems. This decentralization capability fosters a collaborative approach, allowing contributors from different geographical locations to bolster the overall processing power and throughput of our training ecosystem.

### Local Environment Setup <a name="local-setup"></a>
**Redis Integration**: The train node employs Redis to manage and maintain states consistently across the node.

**Docker Integration**: A `docker-compose` file is available to facilitate local testing and development. This file encompasses configurations for both the train node and Redis, ensuring an integrated testing environment.

### Getting Started <a name="getting-started"></a>
#### Prerequisites <a name="prerequisites"></a>
- Ensure you have Docker and Docker Compose installed.


#### Local Setup <a name="local-setup"></a>
- Clone the repository.
- Navigate to the project root.
- Run `docker-compose up` to initiate the Central node, RabbitMQ, PostgreSQL and PGAdmin services.

#### Environment Configuration <a name="environment-configuration"></a>
- Remove the .sample of the env.smaple, that will be loaded by the docker compose.
- Run `docker-compose up` to start the train node along with the Redis instance.


### Conclusion <a name="conclusion"></a>
The train node architecture supports concurrent model training and facilitates easy deployment across various systems, including personal computers. This design not only enhances the training process but also encourages a collaborative, community-driven approach.

