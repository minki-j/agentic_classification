from app.models.object_id import MongoBaseModel
from agents.state import ClassNodeState


# Must inherit from MongoBaseModel first,
# Otherwise, the id field will be serialized as a string instead of an ObjectId
class NodeInDB(MongoBaseModel, ClassNodeState):
    """Node model for MongoDB storage"""

    pass
