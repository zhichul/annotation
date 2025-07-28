import pandas as pd
import annotation.cache as annotation_cache
import uuid
import json

import random

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
FIleOutputHandler = logging.FileHandler("log/human_annotation.log")
logger.addHandler(FIleOutputHandler)

DEFAULT_TASK_NAME = "presentation_demo_0724"


class HumanAnnotationController:
    def __init__(self):
        pass
    
    def load_annotation_tasks(self, file, rounds, task_name):
        subtasks_df = pd.read_csv(file, sep='\t')
        print(subtasks_df)
        
        tasks_list = []
        
        for i in range(0, len(subtasks_df), rounds):
            task_id = str(uuid.uuid4())
            task = []
            
            for j in range(rounds):
                subtask_dict = self._form_a_subtask(task_id, subtasks_df.iloc[i+j])
                task.append(subtask_dict)
                
            annotation_cache.declare_human_annotation_task(task_id, task_name, json.dumps(task))
            print("Added task: " + str(task_id))
            logger.info("Added task: " + str(task_id))

            tasks_list.append(task)
        
        return tasks_list                
                
    def _form_a_subtask(self, task_id, subtask_df):
        subtask = {
            "TaskID": task_id,
            "focus_postID": f"{int(subtask_df['focused_post_id'])}",
        }
                
        candidate_related_posts = []
        for i in range(8):
            candidate_related_posts.append({
                "postID": f"{int(subtask_df['post_id_'+str(i)])}",
                "content": "N/A" if pd.isna(subtask_df['post_rewritten_'+str(i)]) else subtask_df['post_rewritten_'+str(i)],
            })
            
        subtask['candidate_related_posts'] = candidate_related_posts
        
        return subtask
    
    def get_annotation_task(self, user_id, task_name=DEFAULT_TASK_NAME):
        task_id, task_json = annotation_cache.get_human_annotation_task(task_name=task_name, annotator=user_id, max_count=3)
        
        if task_id is None:
            logger.info("No task found for user: " + str(user_id))
            return {
                "status": "TASKS COMPLETED",
                "message": "Tasks completed for user: " + str(user_id)
            }
        
        logger.info("Retrieved task: " + task_id + " for user: " + str(user_id))
        
        data = json.loads(task_json[1:-1])
        
        
        for i in range(len(data)):
            random.shuffle(data[i]["candidate_related_posts"])
        
        random.shuffle(data)
        
        return data
    
    def submit_annotation_task(self, result):        
        user_id = result['tasks'][0]["userID"]
        task_id = result['tasks'][0]["taskID"]
        print(result)
        logger.info("Annotated task: " + str(task_id) + " by user: " + str(user_id))
        annotation_cache.store_human_annotation_result(task_id, user_id, json.dumps(result))
        
        
if __name__ == "__main__":
    human_annotation_controller = HumanAnnotationController()
    print(DEFAULT_TASK_NAME)
    result = human_annotation_controller.load_annotation_tasks("uploads/test_task.tsv", 6, task_name=DEFAULT_TASK_NAME)    