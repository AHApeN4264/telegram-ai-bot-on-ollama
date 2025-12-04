import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
import asyncio
import re
import time
import os
import math
import pickle
from datetime import datetime
from decimal import Decimal, getcontext
import aiohttp
import json

TOKEN = "7599647303:AAH_Nz2SaW3fuGLkgdUakw8yj81JoZukJCQ"

bot = Bot(token=TOKEN)
dp = Dispatcher()

LOGS_DIR = "chat_logs"
HISTORY_FILE = "user_history.pkl"

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

getcontext().prec = 20

user_last_message_time = {}
processed_messages = set()
user_conversation_history = {}
CURRENT_MODEL = None
MESSAGE_COOLDOWN = 2

def load_user_history():
    global user_conversation_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'rb') as f:
                user_conversation_history = pickle.load(f)
        else:
            user_conversation_history = {}
    except Exception as e:
        print(f"Ошибка загрузки истории: {e}")
        user_conversation_history = {}

def save_user_history():
    try:
        with open(HISTORY_FILE, 'wb') as f:
            pickle.dump(user_conversation_history, f)
    except Exception as e:
        print(f"Ошибка сохранения истории: {e}")

def log_message(user_id: int, username: str, message_text: str, is_bot: bool = False):
    filename = f"{LOGS_DIR}/user_{user_id}_{username}.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sender = "🤖 БОТ" if is_bot else f"👤 {username}"
    log_line = f"[{timestamp}] {sender}: {message_text}\n"
    
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Ошибка записи лога: {e}")

async def send_typing_action(chat_id: int, duration: float = 2.0):
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(duration)

def clean_response(text: str) -> str:
    text = re.sub(r'[\u4e00-\u9fff]', '', text)
    text = re.sub(r'[，。、（）【】《》？！：；]', '', text)
    text = re.sub(r'[？：]\d+：', '', text)
    text = re.sub(r'\*{4,}', '', text)
    text = re.sub(r'[-]{3,}', '—', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = text.strip('*_-~`•·')
    return text.strip()

def format_numbered_lists(text: str) -> str:
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            if formatted_lines and formatted_lines[-1] != '':
                formatted_lines.append('')
            continue
        
        if re.match(r'^\d+[\.\)]\s+', line):
            if formatted_lines and formatted_lines[-1] != '':
                formatted_lines.append('')
            formatted_lines.append(line)
        elif re.match(r'^[-•*]\s+', line):
            if formatted_lines and formatted_lines[-1] != '':
                formatted_lines.append('')
            line = re.sub(r'^[-•*]\s+', '• ', line)
            formatted_lines.append(line)
        else:
            formatted_lines.append(line)
    
    result = '\n'.join(formatted_lines)
    result = re.sub(r'(\d+[\.\)]\s+[^\n]+)(?=\d+[\.\)])', r'\1\n', result)
    return result

def format_number(num):
    if isinstance(num, (int, Decimal)):
        if num == int(num):
            return f"{int(num):,}".replace(',', ' ')
        else:
            num_str = f"{float(num):.6f}".rstrip('0').rstrip('.')
            parts = num_str.split('.')
            int_part = f"{int(parts[0]):,}".replace(',', ' ')
            return f"{int_part},{parts[1]}" if len(parts) > 1 else int_part
    return str(num)

def safe_eval(expression: str) -> Decimal:
    try:
        expr = (expression.replace('×', '*').replace('÷', '/')
                         .replace(',', '.').replace(' ', '').replace('\\', '/'))
        if re.search(r'[^0-9+\-*/.()]', expr):
            return None
        result = eval(expr, {"__builtins__": {}}, {})
        return Decimal(str(result))
    except:
        return None

def solve_linear_equation_with_steps(equation: str) -> str:
    try:
        equation = equation.replace(' ', '').replace('=', '==')
        steps = []
        
        if 'x' in equation:
            steps.append(f"🧮 Решаю линейное уравнение:")
            steps.append(f"📝 Уравнение: {equation.replace('==', '=')}")
            steps.append("")
            
            match = re.match(r'x\+(\d+)==(\d+)', equation)
            if match:
                b, c = int(match.group(1)), int(match.group(2))
                steps.append(f"1️⃣ Переносим {b} в правую часть:")
                steps.append(f"   x = {c} - {b}")
                steps.append(f"2️⃣ Вычисляем:")
                steps.append(f"   x = {c - b}")
                return "\n".join(steps)
            
            match = re.match(r'x-(\d+)==(\d+)', equation)
            if match:
                b, c = int(match.group(1)), int(match.group(2))
                steps.append(f"1️⃣ Переносим -{b} в правую часть:")
                steps.append(f"   x = {c} + {b}")
                steps.append(f"2️⃣ Вычисляем:")
                steps.append(f"   x = {c + b}")
                return "\n".join(steps)
            
            match = re.match(r'(\d+)\*x==(\d+)', equation)
            if match:
                a, b = int(match.group(1)), int(match.group(2))
                if a != 0:
                    steps.append(f"1️⃣ Делим обе части на {a}:")
                    steps.append(f"   x = {b} / {a}")
                    steps.append(f"2️⃣ Вычисляем:")
                    steps.append(f"   x = {b / a}")
                    return "\n".join(steps)
            
            match = re.match(r'(\d+)\*x\+(\d+)==(\d+)', equation)
            if match:
                a, b, c = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if a != 0:
                    steps.append(f"1️⃣ Переносим {b} в правую часть:")
                    steps.append(f"   {a}x = {c} - {b}")
                    steps.append(f"2️⃣ Вычисляем правую часть:")
                    steps.append(f"   {a}x = {c - b}")
                    steps.append(f"3️⃣ Делим обе части на {a}:")
                    steps.append(f"   x = {c - b} / {a}")
                    steps.append(f"4️⃣ Вычисляем:")
                    steps.append(f"   x = {(c - b) / a}")
                    return "\n".join(steps)
            
            match = re.match(r'(\d+)\*x-(\d+)==(\d+)', equation)
            if match:
                a, b, c = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if a != 0:
                    steps.append(f"1️⃣ Переносим -{b} в правую часть:")
                    steps.append(f"   {a}x = {c} + {b}")
                    steps.append(f"2️⃣ Вычисляем правую часть:")
                    steps.append(f"   {a}x = {c + b}")
                    steps.append(f"3️⃣ Делим обе части на {a}:")
                    steps.append(f"   x = {c + b} / {a}")
                    steps.append(f"4️⃣ Вычисляем:")
                    steps.append(f"   x = {(c + b) / a}")
                    return "\n".join(steps)
            
            match = re.match(r'(\d+)\*x/(\d+)==(\d+)', equation)
            if match:
                a, b, c = int(match.group(1)), int(match.group(2)), int(match.group(3))
                steps.append(f"1️⃣ Умножаем обе части на {b}:")
                steps.append(f"   {a}x = {c} × {b}")
                steps.append(f"2️⃣ Вычисляем правую часть:")
                steps.append(f"   {a}x = {c * b}")
                steps.append(f"3️⃣ Делим обе части на {a}:")
                steps.append(f"   x = {c * b} / {a}")
                steps.append(f"4️⃣ Вычисляем:")
                steps.append(f"   x = {(c * b) / a}")
                return "\n".join(steps)
        
        return None
    except:
        return None

def solve_quadratic_equation_with_steps(equation: str) -> str:
    try:
        equation = equation.replace(' ', '').replace('x²', 'x^2').replace('x*x', 'x^2')
        steps = []
        
        match = re.match(r'(\d+)x\^2\+(\d+)x\+(\d+)==0', equation)
        if match:
            a, b, c = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return solve_quadratic_with_steps(a, b, c, equation)
        
        match = re.match(r'(\d+)x\^2\+(\d+)x==0', equation)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            return solve_quadratic_with_steps(a, b, 0, equation)
        
        match = re.match(r'(\d+)x\^2\+(\d+)==0', equation)
        if match:
            a, c = int(match.group(1)), int(match.group(2))
            return solve_quadratic_with_steps(a, 0, c, equation)
        
        return None
    except:
        return None

def solve_quadratic_with_steps(a: int, b: int, c: int, equation: str) -> str:
    try:
        steps = []
        steps.append(f"🧮 Решаю квадратное уравнение:")
        steps.append(f"📝 Уравнение: {equation.replace('==', '=')}")
        steps.append("")
        steps.append("1️⃣ Находим дискриминант:")
        steps.append(f"   D = b² - 4ac")
        steps.append(f"   D = {b}² - 4×{a}×{c}")
        
        D = b**2 - 4*a*c
        steps.append(f"   D = {b**2} - {4*a*c}")
        steps.append(f"   D = {D}")
        steps.append("")
        
        if D < 0:
            steps.append("2️⃣ Дискриминант отрицательный:")
            steps.append("   ❌ Уравнение не имеет действительных корней")
            return "\n".join(steps)
        elif D == 0:
            steps.append("2️⃣ Дискриминант равен нулю:")
            steps.append("   Уравнение имеет один корень:")
            steps.append(f"   x = -b / (2a)")
            steps.append(f"   x = -({b}) / (2×{a})")
            x = -b / (2*a)
            steps.append(f"   x = {x}")
            steps.append("")
            steps.append(f"🎯 Ответ: x = {x}")
        else:
            steps.append("2️⃣ Дискриминант положительный:")
            steps.append("   Уравнение имеет два корня:")
            steps.append(f"   x₁ = (-b + √D) / (2a)")
            steps.append(f"   x₂ = (-b - √D) / (2a)")
            steps.append("")
            steps.append("3️⃣ Вычисляем корни:")
            sqrt_D = math.sqrt(D)
            x1 = (-b + sqrt_D) / (2*a)
            x2 = (-b - sqrt_D) / (2*a)
            
            steps.append(f"   x₁ = (-{b} + √{D}) / (2×{a})")
            steps.append(f"   x₁ = (-{b} + {sqrt_D:.2f}) / {2*a}")
            steps.append(f"   x₁ = {(-b + sqrt_D):.2f} / {2*a}")
            steps.append(f"   x₁ = {x1:.2f}")
            steps.append("")
            steps.append(f"   x₂ = (-{b} - √{D}) / (2×{a})")
            steps.append(f"   x₂ = (-{b} - {sqrt_D:.2f}) / {2*a}")
            steps.append(f"   x₂ = {(-b - sqrt_D):.2f} / {2*a}")
            steps.append(f"   x₂ = {x2:.2f}")
            steps.append("")
            steps.append(f"🎯 Ответ: x₁ = {x1:.2f}, x₂ = {x2:.2f}")
        
        return "\n".join(steps)
    except:
        return None

def solve_complex_equation_with_steps(equation: str) -> str:
    try:
        equation = equation.replace(' ', '').replace('=', '==').replace('х', 'x')
        steps = []
        
        if '\\' in equation and 'x' in equation:
            steps.append(f"🧮 Решаю сложное уравнение:")
            steps.append(f"📝 Уравнение: {equation.replace('==', '=')}")
            steps.append("")
            
            parts = [part.strip() for part in equation.split('\\') if part.strip()]
            
            if len(parts) >= 3:
                left_factors = parts[0]
                x_expression = parts[1]
                right_side = parts[2]
                
                steps.append("1️⃣ Вычисляем коэффициенты:")
                
                left_result = safe_eval(left_factors)
                if left_result is None:
                    return None
                steps.append(f"   {left_factors} = {left_result}")
                
                x_coeff_expr = x_expression.replace('x', '').replace('*', '')
                if x_coeff_expr:
                    x_coefficient = safe_eval(x_coeff_expr)
                    if x_coefficient is None:
                        x_coefficient = Decimal(1)
                else:
                    x_coefficient = Decimal(1)
                
                if x_coefficient != 1:
                    steps.append(f"   Коэффициент перед x: {x_coefficient}")
                
                steps.append("")
                steps.append("2️⃣ Составляем уравнение:")
                total_coeff = left_result * x_coefficient
                steps.append(f"   {left_result} × {x_coefficient} × x = {right_side}")
                steps.append(f"   {total_coeff} × x = {right_side}")
                steps.append("")
                steps.append("3️⃣ Решаем относительно x:")
                
                right_num = safe_eval(right_side)
                if right_num is None:
                    return None
                
                steps.append(f"   x = {right_side} / {total_coeff}")
                steps.append(f"   x = {right_num} / {total_coeff}")
                
                x_value = right_num / total_coeff
                steps.append(f"   x = {x_value}")
                steps.append("")
                steps.append(f"🎯 Ответ: x = {x_value:.2f}")
                
                return "\n".join(steps)
        
        return None
    except Exception as e:
        print(f"Ошибка решения сложного уравнения: {e}")
        return None

def solve_equation_with_steps(equation: str) -> str:
    try:
        complex_solution = solve_complex_equation_with_steps(equation)
        if complex_solution:
            return complex_solution
        
        linear_solution = solve_linear_equation_with_steps(equation)
        if linear_solution:
            return linear_solution
        
        quadratic_solution = solve_quadratic_equation_with_steps(equation)
        if quadratic_solution:
            return quadratic_solution
        
        return None
    except Exception as e:
        print(f"Ошибка решения уравнения: {e}")
        return None

def solve_math_expression(expression: str) -> str:
    try:
        if '=' in expression and any(var in expression for var in ['x', 'y', 'z', 'х']):
            equation = expression.replace(' ', '').replace('=', '==').replace('х', 'x')
            equation_result = solve_equation_with_steps(equation)
            if equation_result:
                return equation_result
        
        clean_expr = expression.replace('×', '*').replace('÷', '/').replace(',', '.').replace(' ', '').replace('х', 'x')
        final_result = safe_eval(clean_expr)
        if final_result is None:
            return None
        
        steps = []
        current_expr = clean_expr
        
        steps.append(f"🧮 Решаю математическое выражение:")
        steps.append(f"📝 Выражение: {expression}")
        steps.append("")
        
        while '(' in current_expr:
            bracket_match = re.search(r'\(([^()]+)\)', current_expr)
            if bracket_match:
                sub_expr = bracket_match.group(1)
                sub_result = safe_eval(sub_expr)
                if sub_result is None:
                    break
                steps.append(f"{len(steps)+1}️⃣ Вычисляем в скобках:")
                steps.append(f"   ({sub_expr}) = {format_number(sub_result)}")
                current_expr = current_expr.replace(f'({sub_expr})', str(float(sub_result)))
        
        while re.search(r'[\d.]+\s*[\*/]\s*[\d.]+', current_expr):
            match = re.search(r'([\d.]+)\s*([*/])\s*([\d.]+)', current_expr)
            if match:
                left, op, right = Decimal(match.group(1)), match.group(2), Decimal(match.group(3))
                result = left * right if op == '*' else left / right
                step_text = f"{format_number(left)} {'×' if op == '*' else '÷'} {format_number(right)}"
                steps.append(f"{len(steps)+1}️⃣ {step_text}:")
                steps.append(f"   = {format_number(result)}")
                current_expr = current_expr.replace(match.group(0), str(float(result)), 1)
        
        while re.search(r'[\d.]+\s*[+-]\s*[\d.]+', current_expr):
            match = re.search(r'([\d.]+)\s*([+-])\s*([\d.]+)', current_expr)
            if match:
                left, op, right = Decimal(match.group(1)), match.group(2), Decimal(match.group(3))
                result = left + right if op == '+' else left - right
                step_text = f"{format_number(left)} {op} {format_number(right)}"
                steps.append(f"{len(steps)+1}️⃣ {step_text}:")
                steps.append(f"   = {format_number(result)}")
                current_expr = current_expr.replace(match.group(0), str(float(result)), 1)
        
        if len(steps) == 0:
            steps.append(f"1️⃣ Вычисляем:")
            steps.append(f"   {clean_expr} = {format_number(final_result)}")
        
        steps.append("")
        steps.append(f"🎯 Окончательный ответ: {format_number(final_result)}")
        
        return "\n".join(steps)
        
    except Exception as e:
        print(f"Ошибка решения: {e}")
        return None

def extract_math_expression(text: str) -> str:
    text = re.sub(r'.*(сколько будет|посчитай|вычисли|реши|найди|решение|уравнение)\s*', '', text, flags=re.IGNORECASE).strip()
    
    math_pattern = r'[0-9×÷*\/+\-\s\.\(\)\\xyz=^²х]+'
    matches = re.findall(math_pattern, text)
    if matches:
        expression = max(matches, key=len).strip()
        return re.sub(r'\s*([×÷*\/+\-=])\s*', r'\1', expression)
    return text.strip()

def get_conversation_context(user_id: int) -> str:
    if user_id not in user_conversation_history:
        return ""
    history = user_conversation_history[user_id]
    if not history:
        return ""
    context_lines = []
    for msg in history[-3:]:
        role = msg['role']
        text = msg['text']
        context_lines.append(f"{'Пользователь' if role == 'user' else 'Ассистент'}: {text}")
    return "\n".join(context_lines)

def add_to_history(user_id: int, role: str, text: str):
    if user_id not in user_conversation_history:
        user_conversation_history[user_id] = []
    user_conversation_history[user_id].append({'role': role, 'text': text})
    if len(user_conversation_history[user_id]) > 6:
        user_conversation_history[user_id] = user_conversation_history[user_id][-6:]
    save_user_history()

def check_ollama_availability() -> str:
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            available_models = [model['name'] for model in models]
            
            preferred_models = ["qwen2.5:7b", "llama3.2:latest", "llama3:latest", "mistral:latest"]
            
            for model in preferred_models:
                if model in available_models:
                    return model
            
            if available_models:
                return available_models[0]
            
            return None
        return None
    except Exception as e:
        print(f"Ollama недоступен: {e}")
        return None

def is_phone_number(text: str) -> bool:
    phone_patterns = [
        r'^\+?[78]\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}$',
        r'^\+\d{1,3}\s?\d{1,14}$',
        r'^\d{10,15}$'
    ]
    
    for pattern in phone_patterns:
        if re.match(pattern, text.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')):
            return True
    return False

def is_math_question(text: str) -> bool:
    if is_phone_number(text):
        return False
    
    math_keywords = [
        'посчитай', 'вычисли', 'сколько будет', 'реши', 'найди', 
        'уравнение', 'решение', 'выражение', 'математик'
    ]
    
    math_operators = ['×', '÷', '*', '/', '+', '-', '\\', '=', '^', '²']
    
    math_variables = ['x', 'y', 'z', 'х']
    
    has_numbers = bool(re.search(r'\d+', text))
    
    has_math_keywords = any(keyword in text.lower() for keyword in math_keywords)
    
    has_math_operators = any(op in text for op in math_operators)
    
    has_variables = any(var in text.lower() for var in math_variables)
    
    return (has_math_keywords or 
            (has_math_operators and has_numbers) or
            (has_variables and has_math_operators))

async def search_web(query: str) -> str:
    """Поиск информации в интернете через Google"""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('AbstractText'):
                        abstract = data['AbstractText']
                        if len(abstract) > 100:
                            return f"🔍 Вот что я нашел по запросу '{query}':\n\n{abstract}"
                    
                    if data.get('RelatedTopics'):
                        topics = data['RelatedTopics']
                        if topics and len(topics) > 0:
                            first_topic = topics[0]
                            if 'Text' in first_topic:
                                text = first_topic['Text']
                                if len(text) > 100:
                                    return f"🔍 Вот что я нашел по запросу '{query}':\n\n{text}"
        
        return None
        
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return None

def needs_web_search(text: str) -> bool:
    """Определяет, нужен ли поиск в интернете"""
    search_keywords = [
        'рецепт', 'приготовить', 'как сделать', 'как приготовить', 
        'инструкция', 'руководство', 'советы по', 'что такое',
        'кто такой', 'биография', 'история', 'новости',
        'курс валют', 'погода', 'фильм', 'сериал',
        'отзывы', 'обзор', 'характеристики', 'цена'
    ]
    
    text_lower = text.lower()
    
    has_search_keywords = any(keyword in text_lower for keyword in search_keywords)
    
    specific_requests = [
        'наполеон', 'напалеон', 'торт', 'готовка', 'кулинария'
    ]
    
    has_specific_request = any(request in text_lower for request in specific_requests)
    
    return has_search_keywords or has_specific_request

async def ask_ollama(prompt: str, user_id: int = None) -> str:
    if not prompt or len(prompt.strip()) < 2:
        return "🤔 Запрос слишком короткий."
    
    if is_phone_number(prompt):
        return "📱 Это похоже на номер телефона! Я могу помочь с другими вопросами или математическими задачами 😊"
    
    if needs_web_search(prompt):
        await asyncio.sleep(1)
        search_result = await search_web(prompt)
        if search_result:
            return search_result
    
    is_math = is_math_question(prompt)
    
    if is_math:
        math_expr = extract_math_expression(prompt)
        if math_expr and len(math_expr) >= 2:
            result = solve_math_expression(math_expr)
            if result:
                return result
    
    url = "http://localhost:11434/api/generate"
    context = get_conversation_context(user_id) if user_id else ""
    
    system_prompt = """Ты - полезный и дружелюбный AI-ассистент. Отвечай на русском языке естественно и развернуто, но не слишком длинно.

Твои особенности:
- Отвечай ТОЛЬКО на русском языке
- Будь полезным, информативным и дружелюбным
- Давай развернутые, но не затянутые ответы (3-5 предложений)
- Поддерживай беседу естественно
- Если вопрос непонятен - уточни
- Используй эмодзи для выразительности 😊

Отвечай как умный собеседник, который хочет помочь."""

    if context:
        full_prompt = f"""{system_prompt}

Контекст разговора:
{context}

Текущее сообщение: {prompt}

Твой ответ:"""
    else:
        full_prompt = f"{system_prompt}\n\nСообщение: {prompt}\n\nТвой ответ:"
    
    global CURRENT_MODEL
    if not CURRENT_MODEL:
        CURRENT_MODEL = check_ollama_availability()
        if not CURRENT_MODEL:
            return "❌ Ollama не доступен. Запустите сервер Ollama."
    
    payload = {
        "model": CURRENT_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "top_p": 0.9,
            "num_predict": 500,
            "stop": ["\n\n", "###", "---", "==="]
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code != 200:
            error_msg = f"Ошибка API: {response.status_code}"
            if response.status_code == 404:
                error_msg = "❌ Модель не найдена. Проверьте настройки Ollama."
            elif response.status_code == 500:
                error_msg = "❌ Внутренняя ошибка сервера Ollama."
            return error_msg
            
        data = response.json()
        final_answer = data.get('response', '').strip()
        
        if not final_answer:
            return "🤔 Не получил ответ от модели. Попробуйте еще раз."
        
        final_answer = clean_response(final_answer)
        
        if (len(final_answer.strip()) < 3 or 
            re.search(r'[\u4e00-\u9fff]', final_answer) or
            '****' in final_answer or
            re.search(r'^\d+[\.\)]\s*$', final_answer)):
            return "🤔 Не смог обработать запрос. Попробуйте переформулировать."
        
        final_answer = format_numbered_lists(final_answer)
        
        if len(final_answer) > 1500:
            final_answer = final_answer[:1497] + "..."
        
        return final_answer
        
    except requests.exceptions.Timeout:
        return "⏱ Время ожидания истекло. Попробуйте позже."
    except requests.exceptions.ConnectionError:
        return "🔌 Не могу подключиться к Ollama. Проверьте, запущен ли сервер."
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return "❌ Внутренняя ошибка. Попробуйте еще раз."

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/start")
    log_message(user_id, username, "/start")
    
    welcome_text = (
        "👋 Привет! Я универсальный AI-бот с математическими способностями! 🧮✨\n\n"
        
        "📚 Что я умею:\n"
        "• Отвечать на любые вопросы и поддерживать беседу 💬\n"
        "• Решать математические задачи с подробными объяснениями 🧮\n"
        "• Искать информацию в интернете 🔍\n"
        "• Помогать с учебой, работой и повседневными вопросами 📖\n\n"
        
        "🧮 Математические возможности:\n"
        "• Простые вычисления: 2+2, 15×3\n"
        "• Линейные уравнения: x+5=10, 2x-3=7\n"
        "• Квадратные уравнения: x²-4=0, 2x²+3x-5=0\n"
        "• Сложные выражения: (15+3)×4÷2\n\n"
        
        "🔍 Поиск информации:\n"
        "• Рецепты (наполеон, торты и др.)\n"
        "• Инструкции и руководства\n"
        "• Общая информация\n"
        "• И многое другое!\n\n"
        
        "💡 Просто напиши мне что угодно - вопрос, математическую задачу или просто поболтаем! 😊\n\n"
        "Напиши /help для полной справки."
    )
    
    add_to_history(user_id, "assistant", welcome_text)
    log_message(user_id, username, welcome_text, is_bot=True)
    await message.answer(welcome_text)

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/help")
    log_message(user_id, username, "/help")
    
    help_text = (
        "🤖 Полный список моих возможностей:\n\n"
        
        "💬 ОБЩЕНИЕ:\n"
        "• Отвечаю на любые вопросы\n"
        "• Поддерживаю беседу на разные темы\n"
        "• Помогаю с советами и информацией\n"
        "• Объясняю сложные понятия простыми словами\n\n"
        
        "🔍 ПОИСК В ИНТЕРНЕТЕ:\n"
        "• Рецепты и кулинария\n"
        "• Инструкции и руководства\n"
        "• Общая информация\n"
        "• Ответы на вопросы\n\n"
        
        "🧮 МАТЕМАТИКА:\n"
        "🔹 Базовые операции (с шагами):\n"
        "• 123×456+789\n"
        "• (15+3)×4÷2\n\n"
        "🔹 Линейные уравнения (с объяснением):\n"
        "• x+5=10\n"
        "• 2x-3=7\n"
        "• 3x+2=14\n\n"
        "🔹 Квадратные уравнения (через дискриминант):\n"
        "• x²-4=0\n"
        "• 2x²+3x-5=0\n"
        "• x²+2x+1=0\n\n"
        "🔹 Сложные уравнения:\n"
        "• 2 * 6 \\ 8432 * 356235 \\ х = 7\n\n"
        
        "📊 КОМАНДЫ:\n"
        "/start - начать общение\n"
        "/help - эта справка\n"
        "/status - статус системы\n"
        "/clear - очистить историю\n"
        "/math - примеры математики\n"
        "/chat - примеры общения\n"
        "/search - примеры поиска\n\n"
        
        "💡 Просто напиши мне сообщение - я отвечу на любую тему!"
    )
    
    add_to_history(user_id, "assistant", help_text)
    log_message(user_id, username, help_text, is_bot=True)
    await message.answer(help_text)

@dp.message(Command("search"))
async def search_examples_cmd(message: types.Message):
    """Показывает примеры для поиска"""
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/search")
    log_message(user_id, username, "/search")
    
    examples_text = (
        "🔍 Примеры запросов для поиска:\n\n"
        
        "🍳 КУЛИНАРИЯ:\n"
        "• «Рецепт наполеона»\n"
        "• «Как приготовить торт»\n"
        "• «Рецепт блинов»\n"
        "• «Итальянская паста»\n\n"
        
        "📚 ОБУЧЕНИЕ:\n"
        "• «Что такое искусственный интеллект»\n"
        "• «Как работают нейросети»\n"
        "• «История Древнего Рима»\n"
        "• «Теория относительности»\n\n"
        
        "🔧 ПОЛЕЗНЫЕ СОВЕТЫ:\n"
        "• «Как починить кран»\n"
        "• «Уход за комнатными растениями»\n"
        "• «Советы по изучению языков»\n"
        "• «Эффективные методы обучения»\n\n"
        
        "🌍 ОБЩАЯ ИНФОРМАЦИЯ:\n"
        "• «Биография Пушкина»\n"
        "• «Достопримечательности Парижа»\n"
        "• «Новости технологий»\n"
        "• «Интересные факты о космосе»\n\n"
        
        "🎯 Попробуй любой запрос - я поищу информацию!"
    )
    
    add_to_history(user_id, "assistant", examples_text)
    log_message(user_id, username, examples_text, is_bot=True)
    await message.answer(examples_text)

@dp.message(Command("chat"))
async def chat_examples_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/chat")
    log_message(user_id, username, "/chat")
    
    examples_text = (
        "💬 Примеры тем для общения:\n\n"
        
        "🤔 ОБЩИЕ ВОПРОСЫ:\n"
        "• «Расскажи о искусственном интеллекте»\n"
        "• «Что такое квантовые компьютеры?»\n"
        "• «Как учиться эффективнее?»\n"
        "• «Посоветуй хорошую книгу»\n\n"
        
        "🌍 ПОЗНАВАТЕЛЬНЫЕ:\n"
        "• «Объясни теорию относительности»\n"
        "• «Как работают нейросети?»\n"
        "• «Что такое блокчейн?»\n"
        "• «Расскажи о космосе»\n\n"
        
        "💼 ПОЛЕЗНЫЕ СОВЕТЫ:\n"
        "• «Как написать хорошее резюме?»\n"
        "• «Советы по тайм-менеджменту»\n"
        "• «Как подготовиться к экзамену?»\n"
        "• «Идеи для проекта»\n\n"
        
        "🎯 ЛЮБЫЕ ДРУГИЕ ТЕМЫ!\n"
        "Не стесняйся спрашивать о чем угодно 😊"
    )
    
    add_to_history(user_id, "assistant", examples_text)
    log_message(user_id, username, examples_text, is_bot=True)
    await message.answer(examples_text)

@dp.message(Command("math"))
async def math_examples_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/math")
    log_message(user_id, username, "/math")
    
    examples_text = (
        "📚 Примеры математических запросов:\n\n"
        "🧮 Линейные уравнения:\n"
        "• `x+5=10`\n"
        "• `2x-3=7`\n"
        "• `3x+2=14`\n"
        "• `x-8=2`\n\n"
        "📈 Квадратные уравнения:\n"
        "• `x²-4=0`\n"
        "• `x²+2x+1=0`\n"
        "• `2x²+3x-5=0`\n"
        "• `x²-5x+6=0`\n\n"
        "🔢 Сложные уравнения:\n"
        "• `2 * 6 \\ 8432 * 356235 \\ х = 7`\n"
        "• `3x/2 = 9`\n\n"
        "🔢 Вычисления:\n"
        "• `(15+3)×4÷2`\n"
        "• `2³+5×4`\n"
        "• `√16+8÷2`\n\n"
        "Просто введи любой пример выше!"
    )
    
    add_to_history(user_id, "assistant", examples_text)
    log_message(user_id, username, examples_text, is_bot=True)
    await message.answer(examples_text)

@dp.message(Command("test"))
async def test_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/test")
    log_message(user_id, username, "/test")
    
    await send_typing_action(message.chat.id, 1.0)
    
    test_prompt = "Расскажи о себе в двух предложениях"
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, ask_ollama, test_prompt, None)
    
    response_text = f"🧪 Тест общения:\n\n{answer}"
    
    add_to_history(user_id, "assistant", response_text)
    log_message(user_id, username, response_text, is_bot=True)
    await message.answer(response_text)

@dp.message(Command("clear"))
async def clear_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/clear")
    log_message(user_id, username, "/clear")
    
    if user_id in user_conversation_history:
        user_conversation_history[user_id] = []
        save_user_history()
        response_text = "🗑️ История очищена!"
    else:
        response_text = "✅ История пуста!"
    
    add_to_history(user_id, "assistant", response_text)
    log_message(user_id, username, response_text, is_bot=True)
    await message.answer(response_text)

@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    add_to_history(user_id, "user", "/status")
    log_message(user_id, username, "/status")
    
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        ollama_status = "✅ Доступен" if response.status_code == 200 else "❌ Не доступен"
        if response.status_code == 200:
            version_info = response.json()
            ollama_version = version_info.get('version', 'неизвестно')
        else:
            ollama_version = "неизвестно"
    except:
        ollama_status = "❌ Не доступен"
        ollama_version = "неизвестно"
    
    user_history = user_conversation_history.get(user_id, [])
    user_messages_count = len([msg for msg in user_history if msg['role'] == 'user'])
    
    last_active = user_last_message_time.get(user_id, "никогда")
    if last_active != "никогда":
        last_active = datetime.fromtimestamp(last_active).strftime('%H:%M:%S')
    
    status_text = (
        f"🤖 Статус системы:\n"
        f"• Ollama: {ollama_status}\n"
        f"• Версия Ollama: {ollama_version}\n"
        f"• Модель: {CURRENT_MODEL or 'не выбрана'}\n"
        f"• Ваши сообщения: {user_messages_count}\n"
        f"• Последняя активность: {last_active}\n"
        f"• Логи: {LOGS_DIR}/\n"
        f"• Время: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    add_to_history(user_id, "assistant", status_text)
    log_message(user_id, username, status_text, is_bot=True)
    await message.answer(status_text)

@dp.message(F.text)
async def chat(message: types.Message):
    user_text = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    message_id = message.message_id
    
    if message_id in processed_messages:
        return
    
    processed_messages.add(message_id)
    if len(processed_messages) > 100:
        processed_messages.clear()
    
    current_time = time.time()
    if user_id in user_last_message_time:
        time_since_last = current_time - user_last_message_time[user_id]
        if time_since_last < MESSAGE_COOLDOWN:
            await message.answer(f"⏸ Подожди {MESSAGE_COOLDOWN - int(time_since_last)} сек")
            return
    
    user_last_message_time[user_id] = current_time
    
    add_to_history(user_id, "user", user_text)
    log_message(user_id, username, user_text)
    
    print(f"Вопрос от {username}: {user_text}")
    
    if len(user_text) < 2:
        await message.answer("🤔 Вопрос слишком короткий.")
        return
    
    await send_typing_action(message.chat.id, 1.0)
    
    start_time = time.time()
    
    try:
        answer = await ask_ollama(user_text, user_id)
        
        add_to_history(user_id, "assistant", answer)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        answer = "⚠️ Ошибка. Попробуй еще раз."
        add_to_history(user_id, "assistant", answer)
    
    elapsed_time = round(time.time() - start_time, 1)
    
    print(f"Ответ за {elapsed_time}с")
    log_message(user_id, username, answer, is_bot=True)
    
    time_footer = f"\n\n⏱ {elapsed_time}с"
    
    if len(answer + time_footer) > 4096:
        parts = []
        current_part = ""
        sentences = re.split(r'(?<=[.!?])\s+', answer)
        for sentence in sentences:
            if len(current_part + sentence + time_footer) <= 4096:
                current_part += sentence + " "
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = sentence + " "
        if current_part:
            parts.append(current_part.strip())  

        for part in parts[:-1]:
            await message.answer(part)
        await message.answer(parts[-1].strip() + time_footer)
    else:
        await message.answer(answer + time_footer)

@dp.message(F.photo | F.document | F.video | F.audio)
async def handle_media(message: types.Message):
    username = message.from_user.username or "Аноним"
    user_id = message.from_user.id
    
    media_type = "фото" if message.photo else "документ" if message.document else "видео" if message.video else "аудио"
    
    add_to_history(user_id, "user", f"[{media_type.upper()}]")
    log_message(user_id, username, f"[{media_type.upper()}]", is_bot=False)
    
    response_text = f"📷 Пока работаю только с текстовыми сообщениями. Отправьте текст или вопрос!"
    
    add_to_history(user_id, "assistant", response_text)
    log_message(user_id, username, response_text, is_bot=True)
    await message.answer(response_text)

async def main():
    print("🚀 Бот запускается...")
    print("Загружаем историю сообщений...")
    
    load_user_history()
    
    print("Проверяем доступность Ollama...")
    
    global CURRENT_MODEL
    
    try:
        CURRENT_MODEL = check_ollama_availability()
        if CURRENT_MODEL:
            print(f"✅ Ollama доступен, модель: {CURRENT_MODEL}")
        else:
            print("❌ Ollama не доступен! Запустите: ollama serve")
    except Exception as e:
        print(f"Ошибка проверки Ollama: {e}")
    
    print("🧮 Универсальный AI-бот с математическими способностями")
    print("💬 Поддержка любых тем и вопросов") 
    print("🔍 Поиск информации в интернете")
    print("📈 Математические вычисления с объяснениями")
    print("⌨️ Индикатор печати")
    print("📝 Логирование переписки")
    print("💾 Сохранение истории")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        
        me = await bot.get_me()
        print(f"✅ Бот @{me.username} успешно запущен!")
        print("💬 Готов к общению на любые темы!")
        
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")