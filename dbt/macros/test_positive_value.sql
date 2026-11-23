{# Teste genérico simples (sem depender de pacotes externos): valores devem ser > 0. #}
{% test positive_value(model, column_name) %}
select * from {{ model }} where {{ column_name }} <= 0
{% endtest %}
