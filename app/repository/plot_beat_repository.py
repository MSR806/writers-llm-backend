from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import PlotBeat
from app.utils.exceptions import PlotBeatNotFoundException, rollback_on_exception

from .base_repository import BaseRepository


class PlotBeatRepository(BaseRepository[PlotBeat]):
    def __init__(self, db: Optional[Session] = None):
        super().__init__(db)

    @rollback_on_exception
    def create(self, content: str, type: str, source_id: int) -> PlotBeat:
        plot_beat = PlotBeat(
            content=content,
            type=type,
            source_id=source_id,
        )
        self.db.add(plot_beat)
        self.db.commit()
        self.db.refresh(plot_beat)
        return plot_beat

    @rollback_on_exception
    def batch_create(self, items: List[Dict[str, Any]]) -> List[PlotBeat]:
        plot_beats = []
        for item in items:
            plot_beat = PlotBeat(
                content=item["content"],
                type=item["type"],
                source_id=item["source_id"],
                character_ids=item.get("character_ids", []),  # Handle character_ids
            )
            plot_beats.append(plot_beat)

        self.db.add_all(plot_beats)
        self.db.commit()

        for plot_beat in plot_beats:
            self.db.refresh(plot_beat)

        return plot_beats

    def get_by_source_id_and_type(self, source_id: int, type: str) -> List[PlotBeat]:
        return (
            self.db.query(PlotBeat)
            .filter(PlotBeat.source_id == source_id, PlotBeat.type == type)
            .order_by(PlotBeat.id.asc())
            .all()
        )

    def get_by_id(self, id: int) -> PlotBeat:
        plot_beat = self.db.query(PlotBeat).filter(PlotBeat.id == id).first()
        if not plot_beat:
            raise PlotBeatNotFoundException(f"Plot beat with ID {id} not found")
        return plot_beat

    @rollback_on_exception
    def update(self, plot_beat_id: int, update_data: Dict[str, Any]) -> PlotBeat:
        plot_beat = self.get_by_id(plot_beat_id)
        for key, value in update_data.items():
            if hasattr(plot_beat, key):
                setattr(plot_beat, key, value)

        self.db.commit()
        self.db.refresh(plot_beat)
        return plot_beat
