from flask import Flask, request
from confluent_kafka.admin import AdminClient, NewTopic,ConfigResource
from confluent_kafka import TopicPartition,Consumer
from rich import print
import kafka
import docker
import datetime
from concurrent.futures import ThreadPoolExecutor
app = Flask(__name__)
from operator import itemgetter
def get_partition_size(topic_name: str, partition_key: int):
    topic_partition = TopicPartition(topic_name, partition_key)
    low_offset, high_offset = cons.get_watermark_offsets(topic_partition)
    partition_size = high_offset - low_offset
    return partition_size

def get_topic_size(topic_name: str):
    topic = cons.list_topics(topic=topic_name)
    partitions = topic.topics[topic_name].partitions
    workers, max_workers = [], len(partitions) or 1

    with ThreadPoolExecutor(max_workers=max_workers) as e:
        for partition_key in list(topic.topics[topic_name].partitions.keys()):
            job = e.submit(get_partition_size, topic_name, partition_key)
            workers.append(job)

    topic_size = sum([w.result() for w in workers])
    return topic_size

#compl : O(#(groups))
def calcCurrentOffset():
    topics_in_groups = {}
    client = kafka.KafkaAdminClient(bootstrap_servers=[bootstrap_servers])
    for group in client.list_consumer_groups():
        topics_in_groups[group[0]] = []
    current_offset={}
    for group in topics_in_groups.keys():
        my_topics = []
        current_offset[group] = {}
        topic_dict = client.list_consumer_group_offsets(group)
        for topic in topic_dict:
            index = topic.topic + "|"+str(topic.partition)
            current_offset[group][index]=topic_dict[topic].offset
    # print(current_offset)
    return current_offset

#compl : O(#(partitions))
def calcEndOffeset():
    group_id = 'temp'
    conf = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': group_id
    }
    consumer = Consumer(conf)
    cmeta = consumer.list_topics()
    checkPart=[]
    for topic in topics:
        checkPart =checkPart+[TopicPartition(topic, partition) for partition in cmeta.topics[topic].partitions.keys()]
    ml = {}
    for p in checkPart:
        indexer = p.topic + "|"+str(p.partition)
        ml[indexer]=consumer.get_watermark_offsets(p)[1]
    # print(ml)
    # Close the consumer
    consumer.close()
    return ml

def checkLag(lag,partition,topic,curPos):
    consumer = kafka.KafkaConsumer(topic, bootstrap_servers=bootstrap_servers, enable_auto_commit=True)    
    # consumer.poll()
    tp  = kafka.TopicPartition(topic,int(partition) )
    mapping = consumer.offsets_for_times({tp:delT.timestamp()*1000})
    consumer.close()
    if(mapping[tp]!=None):
        offset = mapping[tp].offset
        c = curPos - offset #messages consumed by consumer in the last delT
        if(c>lag):
            return True
    return False

def calcLag(cur,end):
    topic_lags={}
    for topic in topics:
        topic_lags[topic]=True
    for group, offset in cur.items():
        for partition,curPos in offset.items():
            lag = end[partition]-curPos
            topic = partition.split('|')[0]
            part = partition.split('|')[1]
            # print(group,partition,lag)
            topic_lags[topic]=checkLag(lag,part, topic,curPos) | lag==0
    ntopics = []
    for topic,deletable in topic_lags.items():
        if deletable:
            ntopics.append(topic)
    # print(topic_lags)
    return ntopics

def setRt(topic,newRet):
    config_dict = {'retention.ms': newRet}
    resource = ConfigResource('topic', topic, config_dict)
    result_dict = admin.alter_configs([resource])
    result_dict[resource].result()

def getRt(topic):
    resource = ConfigResource('topic', topic)
    result_dict = admin.describe_configs([resource])
    config_entries = result_dict[resource].result()
    print(topic,str(config_entries['retention.ms']))
        
def getTopics():
    endOffset = calcEndOffeset()
    currOffeset = calcCurrentOffset()
    topics = calcLag(currOffeset,endOffset)
    topicSize = [(topic,get_topic_size(topic)) for topic in topics]
    topicSize=sorted(topicSize,key=itemgetter(1),reverse=True)
    print(topicSize)
    return topics
    
def controller(status):
    if status=="firing":
        ret_ms = 1000
    else:
        ret_ms = 20000
    topicsToChange= getTopics()
    for i in topicsToChange:
        getRt(i)
        setRt(i,ret_ms)
        getRt(i)

def statDisplay():
    client = docker.from_env()
    brokerList = ["kafka101","kafka102","kafka103"]
    print("-----------------------\n")
    for broker in brokerList:
        container = client.containers.get(broker)
        status = container.stats(decode=None, stream = False)
        print(container.name)
        memStats = status['memory_stats']
        memCent = (memStats["usage"]/memStats["limit"])*100
        print("Mem: "+str(memCent))
        # print(status)
    print("-----------------------\n")

@app.route('/alerts', methods=['POST'])
def webhook():
    data = request.json 
    status = data['status']
    print(status)
    print('Received alert:', data)
    if data['receiver']=="Mem_Alert":
        statDisplay()
        controller(status)
        # statDisplay()
    return 'OK'  # Respond with a 200 OK status

if __name__ == '__main__':
    bootstrap_servers = 'localhost:9092'
    admin = AdminClient({'bootstrap.servers': bootstrap_servers})
    consumer = kafka.KafkaConsumer( bootstrap_servers=['localhost:9092'])
    topics=list(consumer.topics())
    consumer.close()
    delT = datetime.datetime.now()-datetime.timedelta(hours=10)
    cons = Consumer({"bootstrap.servers": bootstrap_servers, "group.id": "temp"})
    app.run(host='0.0.0.0', port=5000)

# make c groups, all fine: reduce 1 hr 
# check acc to size 
# print disk usage at each echo
