import { useAdMakerState } from './state/useAdMakerState.js';
import AppShell from './components/AppShell.jsx';
import Home from './screens/Home.jsx';
import Store from './screens/Store.jsx';
import Character from './screens/Character.jsx';
import CharacterInfo from './screens/CharacterInfo.jsx';
import Ad from './screens/Ad.jsx';
import Trend from './screens/Trend.jsx';
import Storyboard from './screens/Storyboard.jsx';
import Result from './screens/Result.jsx';
import MyShell from './screens/My/MyShell.jsx';
import MyStore from './screens/MyStore.jsx';
import InstagramSetup from './screens/InstagramSetup.jsx';

const SCREENS = {
  home: Home,
  store: Store,
  char: Character,
  charInfo: CharacterInfo,
  ad: Ad,
  trend: Trend,
  sb: Storyboard,
  result: Result,
  my: MyShell,
  myStore: MyStore,
  instagram: InstagramSetup
};

export default function App() {
  const { state, actions, charLocked, adLocked } = useAdMakerState();

  if (state.loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6A7077', fontSize: 14 }}>
        불러오는 중…
      </div>
    );
  }

  if (state.loadError) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center', justifyContent: 'center', color: '#2B2F36', fontSize: 14, padding: 24, textAlign: 'center' }}>
        <span style={{ fontWeight: 700 }}>백엔드에 연결하지 못했어요</span>
        <span style={{ color: '#6A7077', fontSize: 13 }}>{state.loadError}</span>
      </div>
    );
  }

  const Screen = SCREENS[state.screen] || Home;
  const missingProdsCount = state.prods.filter(p => !p.soldOut).length;

  return (
    <AppShell state={state} actions={actions} missingProdsCount={missingProdsCount}>
      <Screen state={state} actions={actions} charLocked={charLocked} adLocked={adLocked} />
    </AppShell>
  );
}
