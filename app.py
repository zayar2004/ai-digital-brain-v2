from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta
from config import Config
from models import db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({'error': 'Authorization required', 'reason': reason}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({'error': 'Invalid token', 'reason': reason}), 401

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return jsonify({'error': 'Token expired'}), 401

    # Routes
    from routes import auth_bp, machines_bp, errors_bp, knowledge_bp, tasks_bp, admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(errors_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(admin_bp)

    @app.route('/')
    def root():
        return jsonify({
            'app': 'WorkAI Backend',
            'version': '4.0.0',
            'status': 'running'
        })

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'service': 'WorkAI API'})

    with app.app_context():
        db.create_all()
        # Seed base data (shops + admin)
        from utils.seed import seed_base_data
        seed_base_data()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
