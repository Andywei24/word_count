# WordCount

- This project is the Assignment 2 of TUE-Architecture of Distributed Systems. It implies a distributed system runs in containers. Client may send request to inquire how many times that given word occurs in given file.



## How it works

1. Clone this repo. Currently cannot publish the image because of the policy.

2. Launch with docker:

   ````
   docker-compose up --build
   ````

   ![image-20241005205319781](images/image-20241005205319781.png)

   After everything is ready, you can see log in your console like this, which means the balancer has already recognised 3 servers.

3. Now you can try to send a single request in another console session like this:

   ````
   python client_socket_single.py
   ````

   By run this command, you send 2 requests to a random server (other balance algorithm TBD) forwarded by the balancer.

   1. Send '0' to inquire the files list that the server stores.
   2. Select a random file and select a random word. You may get things like:

   ![image-20241005205402045](images/image-20241005205402045.png)

​	That means the client got a message that says, the word 'a' occurs in pg74503.txt 56 times. Then it disconnects with the balancer.

​	In the container session, you may find log like this:

![image-20241005205528580](images/image-20241005205528580.png)

​	A server received '0', means it should provide the list of files

​	Then it send 'pg74503.txt', 'pg74504.txt', 'pg74505.txt'

​	The balancer forward this msg to the client

​	Then the server received the second request, ask it about how many times that 'a' occurs in 'pg74503.txt'

​	After counting, the server send the answer to the balancer and the balancer forwarded to the client

​	Finally, the balancer disconnected with the client, the server disconnected with the balancer about this request (note: in the meantime the heartbeat between the server and the balancer continuously goes on another port) 

4. You can specify the file name and the word you want to know:

   ````
   python client_socket_single.py pg74504.txt you
   ````

   This command asks how many 'you' in 'pg74504.txt'

5. You can also send many requests simultaneously by run:

   ````
   python client_socket_batch.py
   ````

   Now, it simulates 20 clients send requests in the meantime, each client send 2 requests. 

   40 requests will randomly go to 3 servers. You can check the log to verify this.

6. You can shut a server down in the Docker dashboard

<img src="images/image-20241005211105852.png" alt="image-20241005211105852" style="zoom: 25%;" />

<img src="images/image-20241005211128449.png" alt="image-20241005211128449" style="zoom:50%;" />

for instance, we stop the Server 2



![image-20241005211237413](images/image-20241005211237413.png)

The heartbeat of Server 2 closed at 11:54, after 3 seconds, it removes from the available server list of the balancer.

![image-20241005211519753](images/image-20241005211519753.png)

Then there is no server 2 participatation in the following requests.

7. Then you can relaunch the server 2 in the Docker Dashboard

   <img src="images/image-20241005211727537.png" alt="image-20241005211727537" style="zoom:30%;" />

![image-20241005211820433](images/image-20241005211820433.png)

Then the heartbeat of the Server 2 recovered.

![image-20241005211930246](images/image-20241005211930246.png)

It now can handle requests like before.



## TBD

1. We need to implies 2 algorithms for the balancer. It just randomly chooses server now.
2. We need add redis to cache the latest results to accelerate the repeat requests.
3. We need a list of more word. Now I only use words_list = ["the", "a", "you", "I", "he", "she"]. We can make or download a bigger one.
4. We could add a function that just tell the client the list of file names.
5. We need to test the performance of difference between 1 server, 2 servers, 3 servers and with the Redis cache.
6. The report.



## More txt files?

Just add the download link to the 'links.txt' and re-build the whole image. You can check the download_files.sh for more details.
