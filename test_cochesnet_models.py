from src.import_cars.data import get_cochesnet_models_for_make, get_cochesnet_model_id_by_name

models = get_cochesnet_models_for_make('BMW')
print(f'BMW tiene {len(models)} modelos')

x5_models = [m for m in models if 'X5' in m['label']]
print(f'\nModelos X5:')
for m in x5_models:
    print(f"  {m['id']}: {m['label']}")

model_id = get_cochesnet_model_id_by_name('BMW', 'X5')
print(f'\nID para X5 (búsqueda exacta): {model_id}')

