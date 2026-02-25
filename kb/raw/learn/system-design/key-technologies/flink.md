---
url: https://www.hellointerview.com/learn/system-design/key-technologies/flink
title: Flink
free: true
scraped_at: 2026-02-23T12:15:39.121294Z
---

###### Key Technologies

# Flink

Learn about how you can use Flink to solve a large number of problems in System Design.

*state*to our problem. Each message can't be processed independently because we need to remember the count from previous messages. While we can definitely do this in our service by just holding counters in memory, we've introduced a bunch of new problems.

- As one example of a problem, if our new service crashes it will lose all of its state: basically the count for the preceding 5 minutes is gone. Our service could hypothetically recover from this by re-reading
*all*the messages from the Kafka topic, but this is slow and expensive. - Or another problem is scaling. If we want to add a new service instance because we're handling more clicks, we need to figure out how to re-distribute the state from existing instances to the new ones. This is a complicated dance with a lot of failure scenarios!
- Or what if events come in out of order or late! This is likely to happen and will impact the accuracy of our counts.

*harder*from here as we add complexity and more statefulness. Fortunately, engineers have been building these systems for decades and have come up with useful abstractions. Enter one of the most powerful stream processing engines:

**Apache Flink**.

- First, we're going to talk about how Flink is used. There's a good chance you'll encounter a stream-oriented problem in your interview and Flink is a powerful, flexible tool for the job when it applies.
- Secondly, you'll learn how Flink
*works*, at a high-level, under the hood. Flink solves a lot of problems for you, but for interviews it's important you understand*how*it does that so you can answer deep-dive questions and support your design. We'll cover the important bits.

## Basic Concepts

**operators**and the edges are called

**streams**. We give special names to the nodes at the beginning and end of the graph:

**sources**and

**sinks**. As a developer, your task is to define this graph and Flink takes on the work of arranging the resources to execute the computation.

### Sources/Sinks

**Sources**and

**sinks**are the entry and exit points for data in your Flink application.

**Sources**read data from external systems and convert them into Flink streams. Common sources include:- Kafka: For message queues
- Kinesis: For AWS streaming data
- File systems: For batch processing
- Custom sources: For specialized integrations

**Sinks**write data from Flink streams to external systems. Common sinks include:- Databases: MySQL, PostgreSQL, MongoDB, etc.
- Data warehouses: Snowflake, BigQuery, Redshift
- Message queues: Kafka, RabbitMQ
- File systems: HDFS, S3, local files


### Streams

**Streams**are the edges in your dataflow graph. A stream is an unbounded sequence of data elements flowing through the system. Think of it like an infinite array of events:

```
// Example event in a stream
{
"user_id": "123",
"action": "click",
"timestamp": "2024-01-01T00:00:00.000Z",
"page": "/products/xyz"
}
```


**checkpoints**which the system periodically creates. We'll get into those in more detail on checkpointing later.

### Operators

**operator**is a (potentially)

*stateful*transformation that processes one or more input streams and produces one or more output streams. Operators are the building blocks of your stream processing application. Common operators include:

- Map: Transform each element individually
- Filter: Remove elements that don't match a condition
- Reduce: Combine elements within a key
- Window: Group elements by time or count
- Join: Combine elements from two streams
- FlatMap: Transform each element into zero or more elements
- Aggregate: Compute aggregates over windows or keys

```
DataStream<ClickEvent> clicks = // input stream
clicks
.keyBy(event -> event.getAdId())
.window(TumblingEventTimeWindows.of(Time.minutes(5)))
.reduce((a, b) -> new ClickEvent(a.getAdId(), a.getCount() + b.getCount()))
```


- Takes the input stream of clicks and partitions them by adId using the keyBy operator, creating a KeyedStream
- Applies a tumbling window of 5 minutes to the KeyedStream, which groups elements with the same key that fall within the same 5-minute time period
- Applies a reduce function to each window. This function combines pairs of ClickEvents by creating a new ClickEvent that keeps the adId and adds the count values together

### State

*stateful*, meaning they can maintain internal state across multiple events. This is crucial for any non-trivial stream processing. For example, if you want to count how many times a user has clicked in the last five minutes, you need to maintain state about previous clicks (how many clicks have occurred and when).

**State**needs to be managed internally by Flink in order for the framework to give us scaling and fault tolerance guarantees. When a node crashes, Flink can restore the state from a checkpoint and resume processing from there.

- Value State: A single value per key
- List State: A list of values per key
- Map State: A map of values per key
- Aggregating State: State for incremental aggregations
- Reducing State: State for incremental reductions

```
public class ClickCounter extends KeyedProcessFunction<String, ClickEvent, ClickCount> {
private ValueState<Long> countState;
@Override
public void open(Configuration config) {
ValueStateDescriptor<Long> descriptor =
new ValueStateDescriptor<>("count", Long.class);
countState = getRuntimeContext().getState(descriptor);
}
@Override
public void processElement(ClickEvent event, Context ctx, Collector<ClickCount> out)
throws Exception {
Long count = countState.value();
if (count == null) {
count = 0L;
}
count++;
countState.update(count);
out.collect(new ClickCount(event.getUserId(), count));
}
}
```


- Creates a ClickCounter class that extends KeyedProcessFunction which processes clicks keyed by a String (the userId), takes ClickEvent inputs, and produces ClickCount outputs
- Declares a ValueState<Long> field to store the count of clicks for each user
- In the open method, initializes this state with a descriptor that names the state "count" and specifies its type as Long
- In the processElement method (called for each input event):
- Retrieves the current count from state (or initializes to 0 if null)
- Increments the count
- Updates the state with the new count
- Outputs a new ClickCount object with the user ID and updated count


### Watermarks

- Network delays between event sources
- Different processing speeds across partitions
- Source system delays or failures
- Varying latencies in different parts of the system

- Make decisions about when to trigger window computations
- Handle late-arriving events gracefully
- Maintain consistent event time processing across the distributed system

**Bounded Out-Of-Orderness**: This tells Flink to wait for events that arrive up to a certain time after the event timestamp.**No Watermarks**: This tells Flink to not wait for any late events and process events as they arrive.

### Windows

**Windows**. A window is a way to group elements in a stream by time or count. This is essential for aggregating data in a streaming context. Flink supports several types of windows:

- Tumbling Windows: Fixed-size, non-overlapping windows
- Sliding Windows: Fixed-size, overlapping windows.
- Session Windows: Dynamic-size windows based on activity
- Global Windows: Custom windowing logic

*ends*. If I've created a tumbling window of 5 minute duration and my input is clicks, Flink will emit a new value which includes all the clicks that occurred in the last 5 minutes every 5 minutes.

## Basic Use

### Defining a Job

```
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
// Define source (e.g., Kafka)
DataStream<ClickEvent> clicks = env
.addSource(new FlinkKafkaConsumer<>("clicks", new ClickEventSchema(), properties));
// Define transformations
DataStream<WindowedClicks> windowedClicks = clicks
.keyBy(event -> event.getUserId())
.window(TumblingEventTimeWindows.of(Time.minutes(5)))
.aggregate(new ClickAggregator());
// Define sink (e.g., Elasticsearch)
windowedClicks
.addSink(new ElasticsearchSink.Builder<>(elasticsearchConfig).build());
// Execute
env.execute("Click Processing Job");
```


### Submitting a Job

- Generate a JobGraph: The Flink compiler transforms your logical data flow (DataStream operations) into an optimized execution plan.
- Submit to JobManager: The JobGraph is submitted to the JobManager, which serves as the coordinator for your Flink cluster.
- Distribute Tasks: The JobManager breaks down the JobGraph into tasks and distributes them to TaskManagers.
- Execute: The TaskManagers execute the tasks, with each task processing a portion of the data.

### Sample Jobs

#### Basic Dashboard Using Redis

```
DataStream<ClickEvent> clickstream = env
.addSource(new FlinkKafkaConsumer<>("clicks", new JSONDeserializationSchema<>(ClickEvent.class), kafkaProps));
// Calculate metrics with 1-minute windows
DataStream<PageViewCount> pageViews = clickstream
.keyBy(click -> click.getPageId())
.window(TumblingProcessingTimeWindows.of(Time.minutes(1)))
.aggregate(new CountAggregator());
// Write to Redis for dashboard consumption
pageViews.addSink(new RedisSink<>(redisConfig, new PageViewCountMapper()));
```


#### Fraud Detection System

```
DataStream<Transaction> transactions = env
.addSource(new FlinkKafkaConsumer<>("transactions",
new KafkaAvroDeserializationSchema<>(Transaction.class), kafkaProps))
.assignTimestampsAndWatermarks(
WatermarkStrategy.<Transaction>forBoundedOutOfOrderness(Duration.ofSeconds(10))
.withTimestampAssigner((event, timestamp) -> event.getTimestamp())
);
// Enrich transactions with account information
DataStream<EnrichedTransaction> enrichedTransactions =
transactions.keyBy(t -> t.getAccountId())
.connect(accountInfoStream.keyBy(a -> a.getAccountId()))
.process(new AccountEnrichmentFunction());
// Calculate velocity metrics (multiple transactions in short time)
DataStream<VelocityAlert> velocityAlerts = enrichedTransactions
.keyBy(t -> t.getAccountId())
.window(SlidingEventTimeWindows.of(Time.minutes(30), Time.minutes(5)))
.process(new VelocityDetector(3, 1000.0)); // Alert on 3+ transactions over $1000 in 30 min
// Pattern detection with CEP for suspicious sequences
Pattern<EnrichedTransaction, ?> fraudPattern = Pattern.<EnrichedTransaction>begin("small-tx")
.where(tx -> tx.getAmount() < 10.0)
.next("large-tx")
.where(tx -> tx.getAmount() > 1000.0)
.within(Time.minutes(5));
DataStream<PatternAlert> patternAlerts = CEP.pattern(
enrichedTransactions.keyBy(t -> t.getCardId()), fraudPattern)
.select(new PatternAlertSelector());
// Union all alerts and deduplicate
DataStream<Alert> allAlerts = velocityAlerts.union(patternAlerts)
.keyBy(Alert::getAlertId)
.window(TumblingEventTimeWindows.of(Time.minutes(5)))
.aggregate(new AlertDeduplicator());
// Output to Kafka and Elasticsearch
allAlerts.addSink(new FlinkKafkaProducer<>("alerts", new AlertSerializer(), kafkaProps));
allAlerts.addSink(ElasticsearchSink.builder(elasticsearchConfig).build());
```


## How Flink Works

### Cluster Architecture

#### Job Manager and Task Managers

**Job Manager**is the coordinator of the Flink cluster. It's responsible for scheduling tasks, coordinating checkpoints, and handling failures. Think of it as the "supervisor" of the operation.**Task Managers**are the workers that execute the actual data processing. Each Task Manager provides a certain number of processing slots to the cluster.

- The Job Manager receives the application and constructs the execution graph
- It allocates tasks to available slots in Task Managers
- Task Managers start executing their assigned tasks
- The Job Manager monitors execution and handles failures

#### Task Slots and Parallelism

- They isolate memory between tasks.
- They control the number of parallel task instances.
- They enable resource sharing between different tasks of the same job.

### State Management

*especially*stateful ones) is how to ensure that we can recover from failures without losing data. This is accomplished via Flink's state management system. Let's dive into how it works.

#### State Backends

**Memory State Backend**: Stores state in JVM heap**FS State Backend**: Stores state in filesystem**RocksDB State Backend**: Stores state in RocksDB (supports state larger than memory)

#### Checkpointing and Exactly-Once Processing

- Failure Detection: The Job Manager notices that a Task Manager is no longer sending heartbeats. It marks that Task Manager as failed.
- Job Pause: The entire job is paused. All tasks, even those running on healthy Task Managers, are stopped. This is important because Flink treats the job as a whole unit for consistency.
- State Recovery: Flink retrieves the most recent checkpoint from the state backend (which could be in memory, filesystem, or RocksDB depending on your configuration).
- Task Redistribution: The Job Manager redistributes all the tasks that were running on the failed Task Manager to the remaining healthy Task Managers. It may also redistribute other tasks to balance the load.
- State Restoration: Each task restores its state from the checkpoint. This means every operator gets back exactly the data it had processed up to the checkpoint.
- Source Rewind: Source operators rewind to their checkpoint positions. For example, a Kafka consumer would go back to the offset it had at checkpoint time.
- Resume Processing: The job resumes processing from the checkpoint. Since the checkpoint contains information about exactly which records were processed, Flink guarantees exactly-once processing even after a failure.

## In Your Interview

### Using Flink

- It's usually overkill for simple stream processing. If you just need to transform messages as they flow through Kafka, setting up a service which consumes from Kafka is probably sufficient.
- Flink requires significant operational overhead. You need to consider deployment, monitoring, and scaling of the Flink cluster.
- State management is both Flink's superpower and its biggest operational challenge. Be prepared to discuss how you'll manage state growth and recovery.
- Window choice dramatically impacts both accuracy and resource usage. Be ready to justify your windowing decisions.
- Consider whether you really need exactly-once processing. It comes with performance overhead and complexity.

*everything*as a stream processing job that you can throw into Flink, I wouldn't recommend it. First because many interviewers aren't all familiar with all of Flink's capabilities which might mean they evaluate your solution incorrectly, and secondly because Flink adds complexity overhead which may or may not be appropriate for your problem! Use it where it fits.

### Lessons from Flink

**Separation of Time Domains**: Flink's separation of processing time and event time is a powerful pattern that can be applied to many distributed systems problems.**Watermarks for Progress Tracking**: The watermark concept can be useful in any system that needs to track progress through unordered events.**State Management Patterns**: Flink's approach to state management, including local state and checkpointing, can inform the design of other stateful distributed systems.**Exactly-Once Processing**: The techniques Flink uses to achieve exactly-once processing can be applied to other streaming systems.**Resource Isolation**: Flink's slot-based resource management provides a clean way to isolate and share resources in a distributed system.

## Conclusion

## References

######
