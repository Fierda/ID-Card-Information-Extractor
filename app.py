from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from ocr import main as ocr_main

app = FastAPI()

# Enable CORS for your frontend application (e.g., React on localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend's URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Allow all headers
)

@app.post("/ocr/")
async def upload_file(file: UploadFile = File(...)):
    try:
        output_folder = 'images'
        os.makedirs(output_folder, exist_ok=True)  # Ensure the directory exists

        temp_file_path = os.path.join(output_folder, file.filename)
        
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not os.path.exists(temp_file_path):
            raise HTTPException(status_code=500, detail="File not saved correctly")

        ocr_result = ocr_main(temp_file_path, output_folder)

        os.remove(temp_file_path)

        return JSONResponse(content={"result": ocr_result})

    except Exception as e:
        # Handle errors during the process
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8844)
