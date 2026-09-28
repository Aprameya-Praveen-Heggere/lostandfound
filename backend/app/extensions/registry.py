from .contracts import Extension


class ExtensionRegistry:
    def __init__(self): self._items: dict[str, Extension] = {}
    def register(self, item: Extension): self._items[item.identity] = item
    def list(self):
        return [{"identity": x.identity, "version": x.version, "enabled": x.enabled, "health": x.health()} for x in self._items.values()]
    def dispatch(self, event: str, payload: dict):
        for item in self._items.values():
            if item.enabled and event in item.handlers: item.handlers[event](payload)


registry = ExtensionRegistry()
registry.register(Extension("core.in-app-notifications", "1.0.0"))
registry.register(Extension("matching.local-semantic-hash", "1.0.0", config={"compatible_api":"2.x"}))
registry.register(Extension("image.local-histogram", "1.0.0", config={"face_recognition":False,"compatible_api":"2.x"}))
registry.register(Extension("storage.local-private", "1.0.0", config={"compatible_api":"2.x"}))
registry.register(Extension("email.smtp", "1.0.0", config={"credentials":"environment","compatible_api":"2.x"}))
registry.register(Extension("identity.oidc", "1.0.0", config={"credentials":"environment","compatible_api":"2.x"}))
