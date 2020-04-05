#include <pthread.h>
#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>

#include "threadpool.h"
#include "list.h"


enum f_status {
    UNSCHEDULED, EXECUTING, DONE
};

struct future{
	//the pool this Future is under
    struct Thread_pool *pool;
	// flags
    f_status status; 
    //assoc. task and its parameters
	fork_join_task_t task;
	pthread_cond_t finished;
	//data storage
	void * data;
	void * returnVal;
	struct list_elem elem;
	
};

typedef struct thread {
	pthread_t id;
	//queue of this threads tasks
	struct list queue;
	struct list_elem elem;
} Thread;

struct thread_pool {	
	size_t numWork;
	size_t numThreads;
	// if true destroy
	bool blowUp;
	struct list queue;
	
	//single lock for pool
	pthread_mutex_t pool_lock;
	//condition that there are futures in the queue to be processed
	pthread_cond_t todo_cond;
	//condition that there are no threads currently processing
	pthread_cond_t sitting_cond;
	
	//array of all thread structs
	struct list thread_list;
};


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

static __thread struct thread * curr_thread;

/* Create a new thread pool with no more than n threads. */
struct thread_pool * thread_pool_new(int nthreads) {
	struct thread_pool * tp;
	tp = malloc(sizeof(struct thread_pool));
	
	pthread_mutex_init(&tp->pool_lock, NULL);
	pthread_cond_init(&tp->todo_cond, NULL);
	pthread_cond_init(&tp->sitting_cond, NULL);
	
	list_init(&(tp->queue));
	list_init(&(tp->thread_list))
	tp->blowUp = false;
	tp->numThreads = nthreads;
	tp->numWork = 0;
	
	//lock the pool
	pthread_mutex_lock(&(tp->pool_lock));
	//iterate through and create desired number of threads
	int i = tp->numThreadsl
	while(i != 0){
		struct thread * new_thread;
		new_thread = malloc(sizeof(struct thread));
		list_init(&new_thread->queue);
		list_push_front(&tp->thread_list, &new_thread->elem);
		
		pthread_create(&new_thread->id, NULL, thread_path, tp);
		
	}
	curr_thread = NULL;
	pthread_mutex_unlock(&tp->pool_lock);

	return tp;
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
	pthread_mutex_lock(&pool->pool_lock);
	
	struct future * new_future;
	new_future = malloc(sizeof(struct future));
	pthread_cond_init(&(new_future->finished, NULL));
	
	new_future->status = UNSCHEDULED;
	new_future->task = task;
	new_future->data = data;
	new_future->returnVal = NULL;
	new_future->pool = pool;
	
	//add to either main pool or this theads pool
	if(curr_thread != NULL) {
		list_push_front(&curr_thread->queue);
	}
	else {
		list_push_back(&pool->queue, &new_future->elem)
	}
	
	//add to current number of jobs
	pool->numWork++;
	pthread_cond_signal(&pool->todo_cond);
	pthread_mutex_unlock(&pool->pool_lock);
	
	return new_future;
}

//body of a thread
static void * thread_path(void * arg){
	struct thread_pool * pool = (struct thread_pool *) arg;
	//wait for all threads to be created
	//		TODO MAKE SEMAPHORE
	
	pthread_mutex_lock(&pool->pool_lock);
	pthread_t id = pthread_self();
	struct list_elem * t_elem = list_begin(&(pool->thread_list))
	struct thread * t = NULL;
	while(t_elem != list_end(&(pool->thread_list))){
		t = list_entry(t_elem, struct thread, elem);
		
		if(id == t->id) {
			curr_thread = t;
			break;
		} else {
			t_elem = list_next(t_elem);
		}
	}
	while(1) {
		while(numWork != 0 && !pool->blowUp){
			pthread_cond_wait(&pool->todo_cond), &pool->pool_lock;
		}
		if(pool->blowUp){
			break;
		}
		
		
		struct list_elem * task = NULL;
		
		if(list_empty(&curr_thread->queue)){
			if(list_empty(&pool->queue)){
				//stealing case
				struct list_elem * telem = list_begin(&pool);
				struct thread iterator_thread;
				///find the first non-empty thread queue and 
				///take a task from the back
				while(telem != list_end(&(pool->thread_list))){
					iterator_thread = list_entry(telem, struct thread, elem);
					if(!list_empty(&(iterator_thread->queue))) {
						task = list_pop_back(&iterator_thread->queue));
						break;
					} else {
						telem = list_next(t_elem);
					}
				}
			}
			else{
				task = list_pop_front(&pool->global_queue);
			}
		}
		else {
			task = list_pop_front(&curr_thread->queue)
		}
		
		//task is not either found or NULL
		if (task == NULL){
			pool->shutdown = true;
			break;
		}
		
		//future is found
		struct future * futu = list_entry(task, struct future, elem);
		futu->status = EXECUTING;
		pool->numWork--;
		pthread_mutex_unlock(&pool->pool_lock);
		
		//execute here then lock it back up
		futu->result = futu->task(pool, f->data);
		
		pthread_mutex_lock(&pool->pool_lock);
		futu->status = DONE;
		pthread_cond_signal(&futu->finished);
		
		//unlock and lock back up to give other threads 
		//a chance to execute
		pthread_mutex_unlock(&pool->pool_lock);
		pthread_mutex_t_lock(&pool->pool_lock);
	}
	
	//fin
	pthread_mutex_unlock(&pool->pool_lock);
	pthread_exit(NULL);
	return (NULL);
	
}
/* Make sure that the thread pool has completed the execution
 * of the fork join task this future represents.
 *
 * Returns the value returned by this task.
 */
void * future_get(struct future *){

	return NULL;
}

/* Deallocate this future.  Must be called after future_get() */
void future_free(struct future *) {
	
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
