# main.py

from fastapi import FastAPI

# Создаем экземпляр приложения FastAPI
app = FastAPI(
    title="Parser API",
    description="API for parsing real estate listings and detecting duplicates.",
    version="0.1.0"
)

# Определяем первый эндпоинт (маршрут)
@app.get("/")
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Welcome to the Real Estate Parser API!"}

# Добавим еще один тестовый эндпоинт, чтобы показать, как это работает
@app.get("/status")
async def get_status():
    """
    Returns the current status of the API.
    """
    return {"status": "running", "version": app.version}

