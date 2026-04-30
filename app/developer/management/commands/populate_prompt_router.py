from django.core.management.base import BaseCommand
from developer.models import Intent, Pattern

class Command(BaseCommand):
    help = 'Populate the database with initial prompt router intents and patterns'

    def handle(self, *args, **options):
        # Create intents
        intents_data = {
            'factual': """
## Response shape (factual)

Lead with the specific number or fact. Cite the USDA FoodData Central or Dietary
Guidelines source inline. Keep the answer concise — one to three sentences —
unless the user asks for more detail.
""".strip(),
            'explain': """
## Response shape (explain)

Structure your answer as: what it is → why it matters → how it practically helps
the user. Prefer analogies over jargon. End with one concrete, actionable takeaway.
""".strip(),
            'creative': """
## Response shape (creative)

Offer 2–3 distinct, practical options formatted as a short list. Be enthusiastic and
concrete. Briefly note why each option is a nutritionally sound choice.
""".strip(),
            'goal': """
## Response shape (goal)

Acknowledge the user's goal warmly first. Give 3 prioritized, actionable steps
tailored to that goal. Close by noting that individual needs vary and a registered
dietitian can help create a personalised plan.
""".strip(),
            'general': "",
        }

        for name, prompt in intents_data.items():
            intent, created = Intent.objects.get_or_create(name=name, defaults={'prompt': prompt})
            if created:
                self.stdout.write(f'Created intent: {name}')
            else:
                self.stdout.write(f'Intent already exists: {name}')

        # Create patterns
        patterns_data = [
            ('goal', [
                r"\bi want to\b",
                r"\bi('m| am) trying to\b",
                r"\bmy goal\b",
                r"\blose weight\b",
                r"\bweight loss\b",
                r"\bbuild(ing)? muscle\b",
                r"\bgain(ing)? muscle\b",
                r"\beat (more )?healthier?\b",
                r"\bheart health\b",
                r"\b(manage|control|monitor|track|improve) (my )?blood sugar\b",
                r"\bmy blood sugar\b",
                r"\bmanage (my )?(diabetes|cholesterol|weight)\b",
                r"\bget (more )?energy\b",
                r"\bimprove my (diet|health|nutrition)\b",
                r"\bbetter (diet|nutrition|eating)\b",
            ]),
            ('creative', [
                r"\bwhat can i (make|cook|eat|do) with\b",
                r"\brecipes?\b",
                r"\bmeal ideas?\b",
                r"\bsubstitute for\b",
                r"\bswap (out )?\b",
                r"\bweeknight meals?\b",
                r"\bquick (and easy )?meals?\b",
                r"\bhealthy (snack|breakfast|lunch|dinner|dessert) ideas?\b",
                r"\bwhat (should i|can i) (make|cook|eat)\b",
                r"\bwhat('s| is) (a )?(good|healthy) (recipe|meal|dish)\b",
                r"\bhow (do i|to) (cook|prepare|make)\b",
            ]),
            ('factual', [
                r"\bhow much\b",
                r"\bhow many (calories|grams?|mg|milligrams?|ounces?|servings?)\b",
                r"\bnutrition facts?\b",
                r"\bnutritional (value|info|information|content|profile)\b",
                r"\bwhat vitamins?\b",
                r"\bwhat minerals?\b",
                r"\bprotein in\b",
                r"\bcalories in\b",
                r"\bcarbs? in\b",
                r"\bfat in\b",
                r"\bsodium in\b",
                r"\bfiber in\b",
                r"\bgrams? of\b",
                r"\bvitamin [a-z]\d?\b",
                r"\bnutrients? (in|of|found)\b",
            ]),
            ('explain', [
                r"\bwhy (is|are|does|do|should)\b",
                r"\bhow does\b",
                r"\bhow do\b",
                r"\bwhat does .{1,40} do\b",
                r"\bexplain\b",
                r"\btell me (about|more about|why|how)\b",
                r"\bwhat (is|are) the (benefits?|effects?|role|purpose|function)\b",
                r"\bwhat happens (to|when|if)\b",
                r"\bdifference between\b",
                r"\bwhat is .{1,40} (good|bad|important|used) for\b",
            ]),
        ]

        for intent_name, regexes in patterns_data:
            intent = Intent.objects.get(name=intent_name)
            for regex in regexes:
                pattern, created = Pattern.objects.get_or_create(intent=intent, regex=regex)
                if created:
                    self.stdout.write(f'Created pattern for {intent_name}: {regex}')
                else:
                    self.stdout.write(f'Pattern already exists for {intent_name}: {regex}')

        self.stdout.write(self.style.SUCCESS('Successfully populated prompt router data'))