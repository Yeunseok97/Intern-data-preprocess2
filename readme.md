# 23-gs-006 3,5 assignments image data preprocessing process


## Input data 
- upper body and full body image   



## Model 
- yolov5 segmentation

  1. It should be able to find out how many people are present in the image and count the number of detections for the class "person.
 
  
  2. By using the difference in the min-max y-coordinate values of the person class to calculate the height, it should be compared to half of the height of the original image to determine whether to send it to the "success" or "fail" directory.
 
  3. If there are other animals besides people, it should be processed as a failure.   



★ Since it is an object detection model and processing a large number of images, YOLOv5 segmentation is the most suitable choice.   


★ Since it is pretrained, there is no need for me to perform additional training.






## Unavailable condition   
- More than one person   
    - If the body of someone other than the main person must not be included or detected.   


      
- Height of the Person is 50% or less   
    - The height of the person in the image is less than 50% of the total height of the original image.   
  


## Process flow

1. Check the segment coordinates of the detected classes from the original image using the YOLOv5 L-size model.

2. Verify the number of detected "person" classes; if there is more than one, it results in a failure.

3. Check for the detection of any animal classes other than "person"; if any are detected, it results in a failure.

4. After completing steps 1 and 2, calculate the difference between the max y-coordinate and min y-coordinates of the "person" class segments. If this difference is less than 50% of the original image height, it results in a failure

5. If there are no issues after steps 1,2,3, and 4, mark the process as a success

6. Retrieve the original image file name of the detected file and transfer it to the "success" or "failed" directory based on the success or failure status.

   * After transferring the original file names to the "success" or "failed" directories, convert them into a DataFrame and save the success or fauilure status as a csv file.


## process 5 : detect
![readme_image1](https://github.com/user-attachments/assets/f47903d0-d61b-4407-9825-019d676e7ede)


## process 6 : create CSV 
![csv_image](https://github.com/user-attachments/assets/ca9e594a-82fa-4383-9a1e-54c95e7439c8)


## run
  - predict_run.ipynb
  
      <code> !python3 predict6.py --weights yolov5l-seg.pt --img 640 --conf 0.35 --source /home/selectstar/yolov5/datasets/coco8-pose/images/test --save-txt
## update

### 2024.08.20 

segment predict run file update : predict4.py -> predict6.py
  - height condition operates only Full body image

csv file function update
  - 'success' column was added to explain the specific success status.



### 2024.08.22

- Half image need additional Face detection
  - condition : Face pixel >250000
  - if original face under <250000: upscale openCV or Real esrgan
    
- Face detection with yoloV5 s size model used



### 2024. 98.24

- File path and directory updated

- csv file columns update -> scaled 

### 2024.08.26

- Additional condition of predict.py

- original (Half, Full) image pixel >= 8200000 

- updated -> predict7.py









