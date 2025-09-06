# Team Scaling and Token Management

## Recommended Team Sizes by Plan

Multi-agent systems use ~15x more tokens than standard Claude usage. Team sizes are optimized for sustainable token consumption:

| Plan | Max Agents | Recommended | Notes |
|------|------------|-------------|-------|
| Pro | 3 | 2-3 | Limited token budget |
| Max 5x | 5 | 3-4 | Balance performance/duration (default) |
| Max 20x | 8 | 5-6 | Can support larger teams |
| Console | 10+ | As needed | Enterprise usage |

## Project Size Scaling

| Project Size | Base Roles | Additional Roles | Token Multiplier |
|-------------|------------|------------------|------------------|
| Small | 3-4 | 0-1 optional | 10x |
| Medium | 5-6 | 2-3 optional | 15x |
| Large | 7-8 | 4-5 optional | 20x |
| Enterprise | 9-10+ | All relevant | 25x+ |

## Token Conservation Tips
- Use `--size small` for longer coding sessions
- Check-in intervals increased to conserve tokens (45-90 min)
- Monitor usage with community tools
- Consider serial vs parallel agent deployment for complex tasks

## Using the --plan Flag
```bash
# Specify your subscription plan
./tmux_orchestrator_cli.py run --project /path --spec spec.md --plan max5

# Force small team for extended session
./tmux_orchestrator_cli.py run --project /path --spec spec.md --size small
```

