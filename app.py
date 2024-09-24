from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os

# Importing the main function from ocr.py
from ocr import main as ocr_main

app = FastAPI()

# Endpoint to receive the file and process it using ocr.py
@app.post("/ocr/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Define the directory to save the file, using 'images' instead of '/images'
        output_folder = 'images'
        os.makedirs(output_folder, exist_ok=True)  # Ensure the directory exists

        # Save the file in the images directory
        temp_file_path = os.path.join(output_folder, file.filename)

        # Save the uploaded file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Verify that the file was saved correctly
        if not os.path.exists(temp_file_path):
            raise HTTPException(status_code=500, detail="File not saved correctly")

        # Process the file using your main function
        ocr_result = ocr_main(temp_file_path, output_folder)

        # Remove the file after processing (optional)
        os.remove(temp_file_path)

        # Return the result as a JSON response
        return JSONResponse(content={"result": ocr_result})

    except Exception as e:
        # Handle errors during the process
        raise HTTPException(status_code=500, detail=str(e))

# Running the FastAPI app (optional, if running directly)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8844)
