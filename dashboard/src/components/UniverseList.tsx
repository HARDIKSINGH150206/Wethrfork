import { useStore } from '../state/store'

export function UniverseList() {
  const { universes, order, selected, select } = useStore()
  return (
    <section className="panel universes">
      <h3>Universes</h3>
      <ul>
        {order.map((id) => (
          <li key={id} className={id === selected ? 'sel' : ''} onClick={() => select(id)}>
            {universes[id].name}
            <small> {universes[id].status === 'ready' ? `${Math.round(universes[id].wallMs ?? 0)} ms` : universes[id].status}</small>
          </li>
        ))}
      </ul>
    </section>
  )
}
