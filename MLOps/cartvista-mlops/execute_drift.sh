rm -rfv mlflow.db mlflow.db.bak mlruns.db mlruns/ mlartifacts/ __pycache__/

python generate_data.py

python train_tracked.py --model logreg --C 0.1
python train_tracked.py --model logreg --C 1.0
python train_tracked.py --model logreg --C 10.0
python train_tracked.py --model rf --n-estimators 50  --max-depth 4
python train_tracked.py --model rf --n-estimators 200 --max-depth 8
python train_tracked.py --model rf --n-estimators 400 --max-depth 12
python train_tracked.py --model gb --n-estimators 50 --max-depth 2 --learning-rate 0.8
python train_tracked.py --model gb --n-estimators 100 --max-depth 3 --learning-rate 0.1
python train_tracked.py --model gb --n-estimators 200 --max-depth 6 --learning-rate 0.02

python register_model.py
python consume_model.py
python export_champion.py

# 