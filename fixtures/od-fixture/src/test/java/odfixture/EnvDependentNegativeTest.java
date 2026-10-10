package odfixture;

import org.junit.Test;

/**
 * N3 negative control (ADR-008): models a failure whose real cause is an external environment
 * condition FlakeTrace's controlled re-execution never sets or observes -- e.g. the original
 * bug report's CI system setting an environment variable.
 *
 * Deliberately does NOT check the literal "CI" variable: GitHub Actions sets CI=true on every
 * real runner, so checking that name would make this negative control fail on our own CI job,
 * which is the opposite of the point. FLAKETRACE_N3_NEVER_SET is a fictitious name nothing in
 * this project's toolchain sets, while keeping the same shape: always passes under FlakeTrace,
 * regardless of order or how many times it is repeated. Expected outcome:
 * UNRESOLVED(NOT_REPRODUCED).
 */
public class EnvDependentNegativeTest {
    @Test
    public void onlyFailsUnderCI() {
        if ("true".equals(System.getenv("FLAKETRACE_N3_NEVER_SET"))) {
            throw new AssertionError("would only fail under an environment FlakeTrace never sets");
        }
    }
}
