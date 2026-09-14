from dotenv import load_dotenv
load_dotenv()  # reads mealsense-api/.env (gitignored) — must run before any
                # module reads os.environ, e.g. services/menu_ingestion/
                # llm_enrichment.py's ANTHROPIC_API_KEY lookup

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import recommendations, menu, admin_menu, admin_analytics

app = FastAPI(title="MealSense API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations.router)
app.include_router(menu.router)
app.include_router(admin_menu.router)
app.include_router(admin_analytics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mealsense-api"}
