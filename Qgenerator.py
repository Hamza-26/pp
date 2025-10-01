import random
import json

# Load the JSON data
with open('Question_bank.json') as f:
    data = json.load(f)

# Function to generate a question and its solution
def generate_question(question_type):
    # Find the question template
    question_data = next(q for q in data['questions'] if q['type'] == question_type)
    
    # Generate random values for variables within specified ranges
    variables = {}
    for var, var_data in question_data['variables'].items():
        variables[var] = random.randint(var_data['range'][0], var_data['range'][1])
    
    # Generate the question by replacing placeholders
    question = question_data['template'].format(**variables)
    
    # Solve the question (simplified here, add proper solution logic based on type)
    solution = question_data['solution']
    
    return question, solution, variables

# Example: Generate a linear equation question
question, solution, variables = generate_question('linear_equation')
print("Question:", question)
print("-"*20)
print("Solution:", solution.format(**variables))  # Example of solving