# 23-gs-006 3,5 assignments image data preprocessing process

### "After installing the zip file, you need to download the YOLOvl-seg weights before starting."
<code> !wget https://github.com/ultralytics/yolov5/releases/download/v6.2/yolov5l-seg.pt -O yolov5/Police_assignment/yolov5l-seg.pt </code>

## Flow chart
![3,5 assignments drawio](https://github.com/user-attachments/assets/d4322ac8-75cf-4915-82e3-c3466b2c0f07)

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


  
- Image Size is Less than 8,200,000 Pixels
    - The total pixel count of the image is less than 8,200,000.



## Process flow

1. Check the segment coordinates of the detected classes from the original image using the YOLOv5 L-size model.

2. Verify the number of detected "person" classes; if there is more than one, it results in a failure.

3. Check for the detection of any animal classes other than "person"; if any are detected, it results in a failure.

4. After completing steps 1 and 2, calculate the difference between the max y-coordinate and min y-coordinates of the "person" class segments. If this difference is less than 50% of the original image height, it results in a failure. **This height condition is only applied to full images**.

5. If there are no issues after steps 1,2,3, and 4, mark the process as a success

6. Retrieve the original image file name of the detected file and transfer it to the "success" or "failed" directory based on the success or failure status.

   * After transferring the original file names to the "success" or "failed" directories, convert them into a DataFrame and save the success or fauilure status as a csv file.

7. For half images in steps 1 to 4, before moving them to the success directory, crop the "person" part of the image and save it. Then, perform face detection on the cropped image, and if the number of pixels in the face region is 250,000 or more, mark it as a success; if it is less than 250,000, mark it as a failure. For images that meet the pixel condition, store the original half images in the final success directory.

8. Finally, both the successful half and full images will be stored in their respective directories. By concatenating the CSV files for each process, you can view the list of success and failure files at once.


## process 5 : detect
![readme_image1](https://github.com/user-attachments/assets/f47903d0-d61b-4407-9825-019d676e7ede)
![git_test](https://github.com/user-attachments/assets/0132380b-f9e3-4725-aabf-58533a102edc)


## process 6 : P/F file path
![file_path_directory](https://github.com/user-attachments/assets/04fde059-9316-4935-977f-4547cf921469)


## process 7 : create CSV 
![csv_updated](https://github.com/user-attachments/assets/e838f02b-232b-435e-b0a0-afcb7796589b)



## run
  - predict8_ver3.py
  
      <code> !python3 predict8_ver3.py --weights /home/selectstar/yolov5/Police_assignment/yolov5l-seg.pt --img 640 --conf 0.4 --source /home/selectstar/yolov5/Police_assignment/Raw_data --save-txt --save-crop </code>

  - detect.Face.ipynb

      <code> !python3 detect_Face3.py --weights /home/selectstar/yolov5/Police_assignment/face_detection_yolov5s.pt --source /home/selectstar/yolov5/Police_assignment/Process/Process1/half_class_success --conf 0.4 --save-crop --device 1 </code>


    
## update log

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



### 2024.08.24

- File path and directory updated

- csv file columns update -> scaled 

### 2024.08.26

- Additional condition of predict.py

- original (Half, Full) image pixel >= 8200000 

- updated -> predict7.py

### 2024. 09. 06 

- folder structure upadate
- crop process add
- test in google Colab
- 
### 2024. 10. 08
- predict8_ver4.py update
- Added detection failed case condition
