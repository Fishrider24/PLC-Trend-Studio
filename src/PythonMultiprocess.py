
import multiprocessing as mp
import time

def ilovemike(conn):

    x = 0
    while(1):

        print("I love Mike Brunner")
        x = x + 1
        conn.send(x)
        #conn.close()
        time.sleep(1)
    


def ilovebike():

    print("I love Bike Mooner")

if __name__ == "__main__":
    parent_conn, child_conn = mp.Pipe()
    p1 = mp.Process(target = ilovemike, args = (child_conn,))
    p2 = mp.Process(target = ilovebike)

    p1.start()
    p2.start()
    i = 0

    while i < 10:
        print(parent_conn.recv())
        time.sleep(5)
        i += 1

    

    p1.join()
    p2.join()
