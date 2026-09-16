import { colors } from '../../theme.js';
import HistoryTab from './HistoryTab.jsx';
import ProductionTab from './ProductionTab.jsx';
import DataTab from './DataTab.jsx';

export default function MyShell({ state, actions }) {
  const missingProds = state.prods.filter(p => !p.soldOut);

  const tabButton = (tab, label, badge) => ({
    height: 48, borderRadius: 12, border: 0, fontSize: 15, fontWeight: 700, cursor: 'pointer',
    textAlign: 'left', padding: '0 16px', display: 'flex', alignItems: 'center', gap: 8,
    background: state.myTab === tab ? colors.dark : colors.softBg,
    color: state.myTab === tab ? '#fff' : colors.text
  });

  return (
    <div style={{ padding: 20, display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      <div style={{ flex: '1 1 190px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button onClick={actions.myHistory} style={tabButton('history')}>보관함</button>
        <button onClick={actions.openProdTab} style={tabButton('prod')}>
          생산 기록
          {missingProds.length > 0 && (
            <span style={{ fontSize: 11, fontWeight: 800, background: colors.warnAccent, color: '#fff', borderRadius: 999, padding: '2px 7px' }}>{missingProds.length}</span>
          )}
        </button>
        <button onClick={actions.myStoreTab} style={{ height: 48, borderRadius: 12, border: 0, fontSize: 15, fontWeight: 700, cursor: 'pointer', textAlign: 'left', padding: '0 16px', background: colors.softBg, color: colors.text }}>내 가게 정보</button>
        <button onClick={actions.myChar} style={{ height: 48, borderRadius: 12, border: 0, fontSize: 15, fontWeight: 700, cursor: 'pointer', textAlign: 'left', padding: '0 16px', background: colors.softBg, color: colors.text }}>내 캐릭터 정보</button>
        <button onClick={actions.goData} style={tabButton('data')}>백업 내려받기</button>
      </div>
      <div style={{ flex: '3 1 430px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {state.myTab === 'history' && <HistoryTab state={state} actions={actions} />}
        {state.myTab === 'prod' && <ProductionTab state={state} actions={actions} />}
        {state.myTab === 'data' && <DataTab state={state} actions={actions} />}
      </div>
    </div>
  );
}
