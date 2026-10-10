package odfixture;

import org.junit.Test;
import static org.junit.Assert.assertFalse;

/**
 * F4 victim (ADR-008): class name sorts alphabetically early, so this always runs before
 * {@link ZzzLatePolluterTest} in this project's alphabetical discovery order. The bug can
 * therefore never reproduce in the natural order -- only a shuffled order that happens to
 * place the polluter first can find it.
 */
public class AlwaysEarlyVictimTest {
    @Test
    public void expectsLateFlagUnset() {
        assertFalse(LateFlag.isSet);
    }
}
