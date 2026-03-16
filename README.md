FastAPI Project

This is a backend application built with FastAPI.
Follow the instructions below to set up and run the project locally.

Prerequisites

Before you begin, ensure you have Python 3.8+ installed on your machine.

Getting Started
1. Set Up a Virtual Environment

It is recommended to use a virtual environment to keep dependencies isolated.

Windows
python -m venv venv
.\venv\Scripts\activate
macOS / Linux
python3 -m venv venv
source venv/bin/activate
2. Install Dependencies

Once the virtual environment is activated, install the required packages:

pip install fastapi "uvicorn[standard]" openai python-multipart
3. Run the Application

Start the development server using Uvicorn with hot-reload enabled:

uvicorn main:app --reload

The application will be available at:

http://127.0.0.1:8000

API Documentation

Once the server is running, you can access the interactive API documentation:

Swagger UI

http://127.0.0.1:8000/docs
