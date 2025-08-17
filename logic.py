import sqlite3
from typing import Iterable, List, Optional, Tuple, Dict, Any
from config import DATABASE

# Рендерим карту в headless-окружении
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Cartopy для карты и проекций
import cartopy.crs as ccrs
import cartopy.feature as cfeature


# id, city, lat, lng, country, population (последние поля зависят от структуры вашей БД)
CityRow = Tuple[int, str, float, float, str, int]


class DB_Map:
    def __init__(self, database: str):
        self.database = database

    # ---------- DB utils ----------
    def _connect(self):
        return sqlite3.connect(self.database)

    def create_user_table(self) -> None:
        """Создаёт таблицу users_cities, если её ещё нет."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users_cities (
                    user_id INTEGER NOT NULL,
                    city_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, city_id)
                )
                """
            )
            conn.commit()

    # ---------- Queries over cities catalog ----------
    def _fetchone(self, sql: str, params: Tuple[Any, ...]) -> Optional[tuple]:
        with self._connect() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchone()

    def _fetchall(self, sql: str, params: Tuple[Any, ...] = tuple()) -> list:
        with self._connect() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def get_city_by_name(self, city_name: str) -> Optional[CityRow]:
        """Возвращает строку из справочника cities по имени (без учёта регистра)."""
        row = self._fetchone(
            "SELECT id, city, lat, lng, country, population FROM cities WHERE LOWER(city)=LOWER(?)",
            (city_name.strip(),),
        )
        return row  # type: ignore[return-value]

    def get_coords_by_name(self, city_name: str) -> Optional[Tuple[float, float, str]]:
        """Возвращает (lat, lng, printable_city_name) или None, если город не найден."""
        row = self._fetchone(
            "SELECT lat, lng, city FROM cities WHERE LOWER(city)=LOWER(?)",
            (city_name.strip(),),
        )
        if row:
            lat, lng, name = row
            return float(lat), float(lng), str(name)
        return None

    # ---------- User actions ----------
    def add_city(self, user_id: int, city_name: str) -> bool:
        """
        Добавляет город пользователю. Возвращает True, если город существует в каталоге
        (вставка идемпотентна). False — если город не найден.
        """
        city = self.get_city_by_name(city_name)
        if not city:
            return False
        city_id = int(city[0])
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users_cities (user_id, city_id) VALUES (?, ?)",
                (int(user_id), city_id),
            )
            conn.commit()
        return True

    def select_cities(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список городов пользователя с координатами."""
        rows = self._fetchall(
            """
            SELECT c.city, c.lat, c.lng, c.country
            FROM users_cities uc
            JOIN cities c ON c.id = uc.city_id
            WHERE uc.user_id = ?
            ORDER BY c.city
            """,
            (int(user_id),),
        )
        # Возвращаю и 'lon' и 'lng' (одно и то же значение), чтобы код, который ожидает lon, тоже работал
        return [
            {"city": r[0], "lat": float(r[1]), "lon": float(r[2]), "lng": float(r[2]), "country": r[3]}
            for r in rows
        ]

    # ---------- Rendering ----------
    def create_graph(self, out_path: str, cities: Iterable[Dict[str, Any]]) -> str:
        """
        Рисует карту мира и отмечает точки из `cities` (dict: city, lat, lon|lng).
        Сохраняет PNG по пути out_path и возвращает этот путь.
        """
        cities = list(cities)

        # Создаём карту
        fig = plt.figure(figsize=(10, 5), facecolor="white")
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_global()

        # Базовые слои
        ax.add_feature(cfeature.LAND, zorder=0, edgecolor="black", linewidth=0.2)
        ax.add_feature(cfeature.OCEAN, zorder=0)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.4)
        ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.4)

        # Точки городов
        for item in cities:
            name = str(item.get("city") or item.get("name") or "")
            lat = float(item["lat"])
            # поддерживаем ключ и 'lon', и 'lng'
            lon = float(item.get("lon", item.get("lng")))
            ax.plot(lon, lat, marker="o", markersize=4, transform=ccrs.PlateCarree())
            if name:
                ax.text(lon + 1, lat + 1, name, fontsize=7, transform=ccrs.PlateCarree())

        plt.tight_layout()
        plt.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return out_path

    # На всякий случай — алиас, если где-то в шаблоне опечатка
    def create_grapf(self, out_path: str, cities: Iterable[Dict[str, Any]]) -> str:
        return self.create_graph(out_path, cities)

    def draw_distance(self, city1: str, city2: str, out_path: str) -> Optional[str]:
        """
        (необязательно) Рисует прямую линию между двумя городами.
        Возвращает путь к PNG, если оба города найдены.
        """
        c1 = self.get_coords_by_name(city1)
        c2 = self.get_coords_by_name(city2)
        if not (c1 and c2):
            return None

        lat1, lon1, name1 = c1
        lat2, lon2, name2 = c2

        fig = plt.figure(figsize=(10, 5), facecolor="white")
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_global()
        ax.add_feature(cfeature.LAND, zorder=0, edgecolor="black", linewidth=0.2)
        ax.add_feature(cfeature.OCEAN, zorder=0)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.4)
        ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.4)

        ax.plot([lon1, lon2], [lat1, lat2], transform=ccrs.PlateCarree())
        ax.plot([lon1, lon2], [lat1, lat2], marker="o", linestyle="", transform=ccrs.PlateCarree())
        ax.text(lon1 + 1, lat1 + 1, name1, fontsize=8, transform=ccrs.PlateCarree())
        ax.text(lon2 + 1, lat2 + 1, name2, fontsize=8, transform=ccrs.PlateCarree())

        plt.tight_layout()
        plt.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return out_path


if __name__ == "__main__":
    m = DB_Map(DATABASE)
    m.create_user_table()
