from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Shop(db.Model):
    __tablename__ = 'shops'
    id = db.Column(db.Integer, primary_key=True)
    shop_code = db.Column(db.String(20), unique=True, nullable=False)
    shop_name = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='shop', lazy=True)
    machines = db.relationship('Machine', backref='shop', lazy=True,
                               cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'shopCode': self.shop_code,
            'shopName': self.shop_name,
            'active': self.active,
        }


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'user'
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=True)
    name = db.Column(db.String(100), default='')
    phone = db.Column(db.String(30), default='')
    active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'shopId': self.shop_id,
            'shopCode': self.shop.shop_code if self.shop else None,
            'shopName': self.shop.shop_name if self.shop else None,
            'name': self.name,
            'phone': self.phone,
            'active': self.active,
            'lastLogin': self.last_login.isoformat() if self.last_login else None,
        }


class Machine(db.Model):
    __tablename__ = 'machines'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)
    machine_name = db.Column(db.String(100), nullable=False)
    machine_code = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'shopId': self.shop_id,
            'machineName': self.machine_name,
            'machineCode': self.machine_code,
            'description': self.description,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class ErrorCode(db.Model):
    __tablename__ = 'error_codes'
    id = db.Column(db.Integer, primary_key=True)
    machine_type = db.Column(db.String(100), default='')
    error_code = db.Column(db.String(50), nullable=False)
    error_name = db.Column(db.String(200), nullable=False)
    error_fix = db.Column(db.Text, default='')
    source = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'machineType': self.machine_type,
            'errorCode': self.error_code,
            'errorName': self.error_name,
            'errorFix': self.error_fix,
            'source': self.source,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class Knowledge(db.Model):
    __tablename__ = 'knowledge'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default='')
    category = db.Column(db.String(100), default='')
    source = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category': self.category,
            'source': self.source,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    task_type = db.Column(db.String(20), nullable=False)  # daily/weekly/monthly/yearly
    schedule_date = db.Column(db.BigInteger, default=0)
    weekday = db.Column(db.Integer, default=-1)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=True)
    active = db.Column(db.Boolean, default=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'taskType': self.task_type,
            'scheduleDate': self.schedule_date,
            'weekday': self.weekday,
            'shopId': self.shop_id,
            'active': self.active,
            'completed': self.completed,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
