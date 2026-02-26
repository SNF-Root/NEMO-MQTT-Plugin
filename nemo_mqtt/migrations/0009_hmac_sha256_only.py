# HMAC: use SHA-256 only; remove algorithm choice

from django.db import migrations


def set_hmac_algorithm_sha256(apps, schema_editor):
    MQTTConfiguration = apps.get_model("nemo_mqtt", "MQTTConfiguration")
    MQTTConfiguration.objects.all().update(hmac_algorithm="sha256")


class Migration(migrations.Migration):

    dependencies = [
        ("nemo_mqtt", "0008_fix_qos_level"),
    ]

    operations = [
        migrations.RunPython(set_hmac_algorithm_sha256, migrations.RunPython.noop),
    ]
