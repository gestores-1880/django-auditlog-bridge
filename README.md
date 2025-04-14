# auditlog-bridge
Este paquete facilita la generación de los historiales de los modelos de la aplicación proveyendo una interfaz más sencilla para la configuración de los modelos y la generación de los logs.
Este paquete se basa en el paquete django-auditlog. Más información en https://django-auditlog.readthedocs.io/en/latest/

## Instalación
1. añadir el paquete django-auditlog en la configuración del proyecto, en INSTALLED_APPS
```python
INSTALLED_APPS = [
    ...
    'auditlog',
    ...
]
```
2. aplicar migraciones para crear las tablas necesarias
```bash
python manage.py migrate
```
3. añadir el middleware en el archivo de configuración de la aplicación
```python
MIDDLEWARE = [
    ...
    'auditlog_bridge.middleware.AuditlogBridgeMiddleware',
    ...
]
```
Este middleware se encarga de setear el correlation id en la request para poder identificar y agrupar los logs de una misma petición.

## Uso
1. registrar los modelos que se desean versionar
```python
from django.db import models

from auditlog.registry import auditlog

class MyModel(models.Model):
    pass
    # Model definition goes here

auditlog.register(MyModel)
```
2. en el caso de querer juntar historiales de varios modelos en un solo historial, añadir el método `get_additional_data` en el modelo y referenciar el modelo padre
```python
from django.db import models

from auditlog.registry import auditlog

class MyModel(models.Model):
    def get_additional_data(self):
        return {
            'main_model_id': self.id
        }
auditlog.register(MyModel)

class MyModelRelated(models.Model):
    main_model = models.ForeignKey(MyModel, on_delete=models.CASCADE)
    
    def get_additional_data(self):
        return {
            'main_model_id': self.main_model_id
        }

auditlog.register(MyModelRelated)
```

3. Tener en cuenta que tanto el bulk_create como el bulk_update no generan logs, por lo que es necesario hacer forzar el signal del save de cada objeto. Para ello se puede usar el `SignalQuerySet` en el manager del modelo
```python
from django.db import models

from auditlog.registry import auditlog
from auditlog_bridge.queryset import SignalQuerySet

class MyModel(models.Model):
    objects = SignalQuerySet.as_manager()
    
auditlog.register(MyModel)

MyModel.objects.bulk_create_with_signal([MyModel(), MyModel()])
MyModel.objects.bulk_update_with_signal([MyModel(), MyModel()])
```
También se puede usar el `CelerySignalQuerySet` en el queryset del modelo en caso de que se esté usando Celery. El `CelerySignalQuerySet` es una extensión del `SignalQuerySet` que añade la funcionalidad `bulk_create_with_async_auditlog` que permite crear los logs de forma asíncrona.
```python
    
from django.db import models
from auditlog.registry import auditlog
from auditlog_bridge.celery import CelerySignalQueryset
class MyModel(models.Model):
    objects = CelerySignalQueryset.as_manager()
auditlog.register(MyModel)

MyModel.objects.bulk_create_with_signal([MyModel(), MyModel()])
MyModel.objects.bulk_update_with_signal([MyModel(), MyModel()])
MyModel.objects.bulk_create_with_async_auditlog([MyModel(), MyModel()])

```

4. La clase `HistoryGenerator` es la encargada de generar los historiales de los modelos. Para ello se debe extender de esta clase y sobreescribir las propiedades `version_instance_generator_by_model`, `version_instance_ordering_by_model` y `main_model`. 
   1. La propiedad `version_instance_generator_by_model` debe retornar un diccionario donde la clave es el modelo y el valor es la clase que se encarga de generar la versión del modelo. 
   2. La propiedad `version_instance_ordering_by_model` debe retornar un diccionario donde la clave es el modelo y el valor es una lista con los campos por los que se ordenarán las versiones del modelo.
   3. La propiedad `main_model` debe retornar el modelo principal en caso de que se desee agrupar los historiales de varios modelos. En caso de no querer agrupar los historiales, se puede omitir esta propiedad.
```python
class MyModelHistoryGenerator(HistoryGenerator):
    version_instance_generator_by_model = {
        MyModel: MyModelVersionInstanceGenerator,
    }
    version_instance_ordering_by_model = {
        MyModel: 1,
    }
    main_model = MyModel
```
La clase `VersionInstanceGenerator` es la encargada de generar las versiones de los modelos. Podemos extender de esta clase y sobreescribir el método `_custom_generator`. Este método recibe como parámetro el `LogEntry`, la `VersionInstance` y el `context`.
```python
class MyModelVersionInstanceGenerator(VersionInstanceGenerator):
    def _custom_generator(self, log: LogEntry, version_instance: VersionInstance, context: dict):
        pass
```

5. Y por último, añadir el mixin `AuditLogBridgeMixin` a la clase de la vista que se desee auditar. Este mixin añade una action `history` que se encarga de retornar el historial del modelo. Para configurar la acción hay que añadir las propiedades `history_generator_model`, `history_option` y `history_generator_filter` a la vista.
```python
from auditlog_bridge.mixins import AuditLogBridgeMixin

class MyModelView(AuditLogBridgeMixin, View):
    history_generator_model = MyModelHistoryGenerator
    history_option = 'GROUPED' # Valores posibles: 'GROUPED', 'SINGLE'
    history_generator_filter = 'my_model_id' # Requerido si history_option es 'GROUPED'
    exclude_cid_starting_with = 'exclude_cids' # Opcional, si se desea excluir los logs que empiezan con un cid determinado
```
La url para obtener el historial del modelo es `/<pk>/history/`

## Issues

### Instance duplication

If you are duplication a django model instance, removing the `id` field and saving it again, the auditlog think you are updating the instance and not creating a new one. To avoid this, fix the _state of the instance to be saved.

```python
instance = MyModel.objects.get(pk=1)
instance.pk = None
instance._state.adding = True
instance.save()
```