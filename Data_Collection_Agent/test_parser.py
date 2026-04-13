from Data_Collection_Agent.brain.prompt_parser import PromptParser
p = PromptParser()

# Test 1: explicit input/output
r = p.parse('Build a movie recommendation system. input: genre, rating. output: list of recommended movies')
print('Test 1 - input_params:', r['input_params'])
print('Test 1 - output_description:', r.get('output_description', 'NOT SET'))
assert 'genre' in r['input_params'], f'Missing genre in {r["input_params"]}'
assert 'rating' in r['input_params'], f'Missing rating in {r["input_params"]}'
assert r.get('output_description'), 'output_description not set'
print('PASS: Test 1')

# Test 2: no directive (old-style prompt still works)
r2 = p.parse('Build a movie recommendation system using genre and rating')
print('Test 2 - input_params:', r2['input_params'])
assert 'genre' in r2['input_params'] or 'rating' in r2['input_params']
print('PASS: Test 2')
