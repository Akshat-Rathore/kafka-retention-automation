from flask import Flask, request
from confluent_kafka.admin import AdminClient, NewTopic,ConfigResource
from confluent_kafka import TopicPartition,Consumer
from rich import print
import kafka
import docker

app = Flask(__name__)

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
    print(current_offset)
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
    print(ml)
    # Close the consumer
    consumer.close()
    return ml

def calcLag(cur,end):
    topic_lags={}
    for topic in topics:
        topic_lags[topic]=True
    for group, offset in cur.items():
        for partition,val in offset.items():
            lag = end[partition]-val
            topic = partition.split('|')[0]
            print(group,partition,lag)
            if lag!=0:
                topic_lags[topic]=False
    ntopics = []
    for topic,deletable in topic_lags.items():
        if deletable:
            ntopics.append(topic)
    print(topic_lags)
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
    
    app.run(host='0.0.0.0', port=5000)

# make c groups, all fine: reduce 1 hr 
# check acc to size 
# print disk usage at each echo
