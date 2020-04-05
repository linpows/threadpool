#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <semaphore.h>
#include "threadpool.h"
#include "list.h"


enum f_status {
    UNSCHEDULED, EXECUTING, DONE
};

typedef struct {
	//the pool this Future is under
    struct Thread_pool *pool;
	// flags
    __thread int number;
    f_status status; 
    sem_t done;
    sem_t got;
    //assoc. task and its parameters
	fork_join_task_t task;
	void * data;
	//used for list
	struct list_elem elem;
	
} Future;

typedef struct {	
	size_t numWorking;
	size_t numThreads;
	// if true destroy
	bool blowUp;
	struct list queue;
	
	//single lock for pool
	pthread_mutex_t pool_mutex;
	//condition that there are futures in the queue to be processed
	pthread_cond_t todo_cond;
	//condition that there are no threads currently processing
	pthread_cond_t sitting_cond;
	
	//array of all thread structs
	Thread pool[];
} Thread_pool;

struct thread;
typedef struct {
	// need thread local variable, also unsure 
	//if structs are needed for threads, or if they 
	//are created as functions.
	struct list queue;
	//thread to lock it down.
	pthread_mutex_t thread_mutex;
} Thread;


/** USEFULL FUNCTIONS
 * //add to
	void list_push_front (struct list *, struct list_elem *);
	void list_push_back (struct list *, struct list_elem *);
 * //operations
	struct list_elem *list_remove (struct list_elem *);
	struct list_elem *list_pop_front (struct list *);
	struct list_elem *list_pop_back (struct list *);
 * //status check
	size_t list_size (struct list *);
	bool list_empty (struct list *);
 * //look at elems
	struct list_elem *list_front (struct list *);
	struct list_elem *list_back (struct list *);
	
	* ///TO INITIALIZE 
	* //job_list = malloc(sizeof(struct list));
	* //list_init(job_list); 
	*/


struct thread_pool;
struct future;

/* Create a new thread pool with no more than n threads. */
struct thread_pool * thread_pool_new(int nthreads) {
	//TODO
	return NULL;
}

/* 
 * Submit a fork join task to the thread pool and return a
 * future.  The returned future can be used in future_get()
 * to obtain the result.
 * 'pool' - the pool to which to submit
 * 'task' - the task to be submitted.
 * 'data' - data to be passed to the task's function
 *
 * Returns a future representing this computation.
 */
struct future * thread_pool_submit(struct thread_pool *pool,
									fork_join_task_t task, void * data){
	
	return NULL;
}

/* Make sure that the thread pool has completed the execution
 * of the fork join task this future represents.
 *
 * Returns the value returned by this task.
 */
void * future_get(struct future * f){
	sem_wait(&(f->done));
	sem_post(&(f->got));
	return f->data;
}

/* Deallocate this future.  Must be called after future_get() */
void future_free(struct future *) {
	sem_wait(&(f->got));
	free(&(f->data));
	free(f);
	f = NULL;
}

/* 
 * Shutdown this thread pool in an orderly fashion.  
 * Tasks that have been submitted but not executed may or
 * may not be executed.
 *
 * Deallocate the thread pool object before returning. 
 */
void thread_pool_shutdown_and_destroy(struct thread_pool *){
	//TODO
}
