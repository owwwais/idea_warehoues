import pyrebase

config = {
    "apiKey": "AIzaSyAFe3t7G7xEUUggL2xy4yufhRcnVUojskA",
    "authDomain": "sand-task-4q9bty.firebaseapp.com",
    "projectId": "sand-task-4q9bty",
    "storageBucket": "sand-task-4q9bty.appspot.com",
    "messagingSenderId": "413074085567",
    "appId": "1:413074085567:web:39eb6757dccd37047d180a",
    "databaseURL": "https://sand-task-4q9bty-default-rtdb.asia-southeast1.firebasedatabase.app"
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
storage = firebase.storage()

# تصدير الوظائف المطلوبة
__all__ = ['auth', 'db', 'storage']
