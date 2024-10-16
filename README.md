# word_count
  Architecture of Distributed System

## 1. Select an algorithm in balancer.py (weighted or hash)
<image src = "./images/select.png">
  
## 2. Launch the server
```
  docker-compose up --build
```
<image src = "./images/create.png">
  Check the server weighted
  <image src = "./images/weighted.png"

## 3. Send request
```
python client_socket_single.py
```
<image src = "./images/client.png">

## 4. See how the server handle the request
<image src = "./images/server.png">

## 5. Check the data in redis
```
docker ps
redis-cli
KEYS *
GET pg74505.txt:the
ZRANGE word_count 0 -1 WITHSCORES
```
<image src = "./images/redis.png">
<image src = "./images/key.png">
<image src = "./images/word_count.png">

