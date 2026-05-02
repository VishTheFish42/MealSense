from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import recommendations, menu

app = FastAPI(title="MealSense API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations.router)
app.include_router(menu.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mealsense-api"}
