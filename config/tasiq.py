from taskiq_nats import PullBasedJetStreamBroker

# PullBasedJetStreamBroker позволяет нескольким воркерам (worker-0, worker-1)
# параллельно забирать задачи из одного стрима без конфликта 'consumer name already in use'.
broker = PullBasedJetStreamBroker(
    servers=["nats://localhost:4222"],
    subject="taskiq_tasks",
    stream_name="taskiq_jetstream",
    durable="taskiq_durable",
)


async def get_kv():
    """Возвращает Key-Value хранилище NATS JetStream для отслеживания прогресса задач."""
    js = broker.client.jetstream()
    try:
        return await js.key_value("task_progress")
    except Exception:
        return await js.create_key_value(bucket="task_progress", history=1, ttl=3600)
