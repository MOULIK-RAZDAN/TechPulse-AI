from kafka import KafkaConsumer, KafkaProducer
import json
from datasketch import MinHash, MinHashLSH
import redis

class DeduplicationService:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'raw_articles',
            bootstrap_servers=['kafka:9092'],
            group_id='dedup-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        self.producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.redis_client = redis.Redis(host='redis', port=6379, password='changeme', decode_responses=True)
        self.lsh = MinHashLSH(threshold=0.95, num_perm=128)
    
    def create_minhash(self, text):
        minhash = MinHash(num_perm=128)
        words = text.lower().split()
        for i in range(len(words) - 2):
            minhash.update((' '.join(words[i:i+3])).encode('utf-8'))
        return minhash
    
    def is_duplicate(self, article):
        content = f"{article['title']} {article['content']}"
        minhash = self.create_minhash(content)
        similar = self.lsh.query(minhash)
        
        if similar:
            return True
        else:
            self.lsh.insert(article['article_id'], minhash)
            self.redis_client.set(f"minhash:{article['article_id']}", json.dumps(minhash.hashvalues.tolist()), ex=604800)
            return False
    
    def run(self):
        print("Deduplication service started")
        for message in self.consumer:
            article = message.value
            if not self.is_duplicate(article):
                self.producer.send('embedded_articles', value=article)
                print(f"Unique: {article['title']}")

if __name__ == '__main__':
    service = DeduplicationService()
    service.run()
